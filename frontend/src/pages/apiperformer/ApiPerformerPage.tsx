import { useEffect, useMemo, useState } from 'react';
import {
  App as AntApp,
  Alert,
  Breadcrumb,
  Button,
  Card,
  Col,
  Collapse,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Radio,
  Row,
  Select,
  Space,
  Tabs,
  Tag,
  Tree,
  Typography,
} from 'antd';
import type { TreeDataNode } from 'antd';
import {
  ApiOutlined,
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
  FileAddOutlined,
  FolderAddOutlined,
  FolderOutlined,
  FormatPainterOutlined,
  GlobalOutlined,
  PlusOutlined,
  SendOutlined,
} from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import { KeyValueListEditor } from '../../components/KeyValueListEditor';
import { JsonOrPlainView } from '../../components/JsonView';
import { useEnvironments } from '../../hooks/useEnvironments';
import {
  useCreateSavedRequest,
  useDeleteSavedRequest,
  useExecuteAdHocRequest,
  useUpdateSavedRequest,
} from '../../hooks/useApiPerformer';
import {
  useApiCollectionsTree,
  useCreateCollection,
  useCreateFolder,
  useDeleteCollection,
  useDeleteFolder,
  useUpdateCollection,
  useUpdateFolder,
} from '../../hooks/useApiCollections';
import { getSavedRequest } from '../../api/apiPerformer';
import { ApiError } from '../../api/client';
import { HTTP_METHODS, HTTP_METHOD_COLORS, methodColor } from '../../constants/httpMethod';
import type {
  ApiCollectionTreeNode,
  ApiExecuteResult,
  ApiRequestMethod,
  SavedApiRequest,
} from '../../api/types';

const { Title, Text } = Typography;

/** Postman-style body format sub-option. `raw` and `json` both send the body text as-is (see `handleSend`) — `json` just gets the "Beautify" affordance and highlighted-as-JSON treatment leaned into; `graphql` is a simplified single-textarea mode (no separate query/variables split). */
type BodyMode = 'raw' | 'json' | 'graphql';

interface BuilderState {
  method: ApiRequestMethod;
  url: string;
  environmentId: string | undefined;
  headers: Record<string, string>;
  queryParams: Record<string, string>;
  body: string;
  bodyMode: BodyMode;
}

const BLANK_BUILDER: BuilderState = {
  method: 'GET',
  url: '',
  environmentId: undefined,
  headers: {},
  queryParams: {},
  body: '',
  bodyMode: 'json',
};

/** Where a "+" on a collection/folder node in the tree targets a newly-built request for saving. */
interface CreateTarget {
  collectionId: string;
  folderId?: string;
}

/** Local state for the single shared rename/create-name modal used by every tree node action. */
type NodeModalState =
  | { mode: 'new-collection' }
  | { mode: 'new-folder'; collectionId: string }
  | { mode: 'rename-collection'; id: string }
  | { mode: 'rename-folder'; id: string; collectionId: string }
  | null;

function statusTagColor(statusCode: number | null): string {
  if (statusCode === null) return 'error';
  if (statusCode >= 200 && statusCode < 300) return 'success';
  if (statusCode >= 300 && statusCode < 400) return 'blue';
  if (statusCode >= 400 && statusCode < 500) return 'warning';
  return 'error';
}

/** A tree row: main content on the left, hover-revealed action icons on the right (see the `.api-tree-node` CSS below). */
function TreeNodeRow({
  testId,
  children,
  actions,
}: {
  testId: string;
  children: React.ReactNode;
  actions: React.ReactNode;
}) {
  return (
    <span
      className="api-tree-node"
      data-testid={testId}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        width: '100%',
      }}
    >
      <span style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
        {children}
      </span>
      <span
        className="api-tree-node-actions"
        style={{ display: 'flex', gap: 2, flexShrink: 0 }}
        onClick={(e) => e.stopPropagation()}
      >
        {actions}
      </span>
    </span>
  );
}

/**
 * Sprint 9: API Performer redesigned as a genuine Postman-style layout —
 * three bordered Cards (Collections sidebar / Request Builder / Response)
 * instead of one continuous unstyled column, and saved requests organized
 * as Collection -> Folder (optional, one level) -> Request instead of a
 * flat list. Ad-hoc "Send" still never requires saving first.
 *
 * Scope cut: there is no dedicated "move request between folders/collections"
 * action this sprint. A request's collection is fixed at creation
 * (`collection_id` isn't patchable per the backend contract); moving a
 * request to a different folder within the *same* collection isn't exposed
 * in the UI either — to relocate a request, delete and recreate it in the
 * target collection/folder. This keeps the tree's create/rename/delete
 * affordances (the sprint's actual ask) simple to reason about.
 */
export default function ApiPerformerPage() {
  const { projectId } = useParams();
  const { message } = AntApp.useApp();

  const { data: tree, isLoading: treeLoading } = useApiCollectionsTree(projectId);
  const { data: environments, isLoading: environmentsLoading } = useEnvironments(projectId);

  const createSavedRequest = useCreateSavedRequest(projectId);
  const updateSavedRequest = useUpdateSavedRequest(projectId);
  const deleteSavedRequest = useDeleteSavedRequest(projectId);
  const executeAdHoc = useExecuteAdHocRequest(projectId);

  const createCollection = useCreateCollection(projectId);
  const updateCollection = useUpdateCollection(projectId);
  const deleteCollection = useDeleteCollection(projectId);
  const createFolder = useCreateFolder(projectId);
  const updateFolder = useUpdateFolder(projectId);
  const deleteFolder = useDeleteFolder(projectId);

  const [builder, setBuilder] = useState<BuilderState>(BLANK_BUILDER);
  const [loadedRequest, setLoadedRequest] = useState<SavedApiRequest | null>(null);
  const [loadingRequestId, setLoadingRequestId] = useState<string | null>(null);
  const [response, setResponse] = useState<ApiExecuteResult | null>(null);

  // Where a brand-new request (started via a tree node's "+") should be saved.
  const [createTarget, setCreateTarget] = useState<CreateTarget | null>(null);

  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saveCollectionId, setSaveCollectionId] = useState<string | undefined>(undefined);
  const [saveFolderId, setSaveFolderId] = useState<string | undefined>(undefined);

  const [nodeModal, setNodeModal] = useState<NodeModalState>(null);
  const [nodeModalName, setNodeModalName] = useState('');

  const collections = useMemo(() => tree ?? [], [tree]);

  // The tree is a controlled `expandedKeys` set rather than relying on antd's
  // `defaultExpandAll` (which only computes its initial expanded set once,
  // at mount) — every mutation (create/delete a folder or request) refetches
  // `tree` and, without this, previously-visible nodes would silently
  // collapse back to just the top-level collections after every action,
  // which reads as "my folder disappeared." Newly-seen keys (a just-created
  // collection/folder) are unioned in automatically; a key a user explicitly
  // collapsed stays collapsed across unrelated mutations.
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
  useEffect(() => {
    if (!tree) return;
    const allKeys: string[] = [];
    for (const coll of tree) {
      allKeys.push(`collection:${coll.id}`);
      for (const folder of coll.folders) {
        allKeys.push(`folder:${folder.id}`);
      }
    }
    setExpandedKeys((prev) => {
      const prevSet = new Set(prev);
      const next = [...prev];
      for (const key of allKeys) {
        if (!prevSet.has(key)) next.push(key);
      }
      return next;
    });
    // Only re-derive when the set of collections/folders itself changes, not
    // on every tree refetch with identical structure.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tree?.map((c) => `${c.id}:${c.folders.map((f) => f.id).join(',')}`).join('|')]);

  const handleNewRequest = () => {
    setBuilder(BLANK_BUILDER);
    setLoadedRequest(null);
    setCreateTarget(null);
    setResponse(null);
  };

  const handleSelectRequestNode = async (requestId: string) => {
    if (!projectId) return;
    setLoadingRequestId(requestId);
    try {
      const req = await getSavedRequest(projectId, requestId);
      setLoadedRequest(req);
      setCreateTarget(null);
      setBuilder({
        method: req.method as ApiRequestMethod,
        url: req.url,
        environmentId: req.environment_id ?? undefined,
        headers: req.headers,
        queryParams: req.query_params,
        body: req.body ?? '',
        bodyMode: 'json',
      });
      setResponse(null);
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    } finally {
      setLoadingRequestId(null);
    }
  };

  const handleStartNewRequestIn = (target: CreateTarget) => {
    setBuilder(BLANK_BUILDER);
    setLoadedRequest(null);
    setCreateTarget(target);
    setResponse(null);
    message.info('Building a new request — use Save below to add it here.');
  };

  const handleDeleteRequest = async (requestId: string) => {
    try {
      await deleteSavedRequest.mutateAsync(requestId);
      message.success('Request deleted');
      if (loadedRequest?.id === requestId) {
        handleNewRequest();
      }
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleSend = async () => {
    if (!builder.url.trim()) {
      message.warning('Enter a URL');
      return;
    }
    try {
      const result = await executeAdHoc.mutateAsync({
        method: builder.method,
        url: builder.url,
        headers: builder.headers,
        query_params: builder.queryParams,
        body: builder.body || undefined,
        environment_id: builder.environmentId,
      });
      setResponse(result);
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  /** Pretty-prints `builder.body` in place if it's valid JSON; otherwise leaves it untouched and tells the user why (never throws on malformed input). */
  const handleBeautifyBody = () => {
    if (!builder.body.trim()) return;
    try {
      const pretty = JSON.stringify(JSON.parse(builder.body), null, 2);
      setBuilder((b) => ({ ...b, body: pretty }));
    } catch {
      message.info('Body is not valid JSON — nothing to beautify.');
    }
  };

  // Breadcrumb path (Collection > Folder > Request) for the currently-loaded saved request.
  // Unsaved / ad-hoc requests (and ones being built into an as-yet-unpicked create target)
  // render no breadcrumb — see the "Unsaved Request" fallback below.
  const requestPath = useMemo(() => {
    if (!loadedRequest) return null;
    const coll = collections.find((c) => c.id === loadedRequest.collection_id);
    const folder = loadedRequest.folder_id
      ? coll?.folders.find((f) => f.id === loadedRequest.folder_id)
      : undefined;
    return {
      collectionName: coll?.name ?? 'Collection',
      folderName: folder?.name,
      requestName: loadedRequest.name,
    };
  }, [loadedRequest, collections]);

  const buildSaveInput = () => ({
    method: builder.method,
    url: builder.url,
    headers: builder.headers,
    query_params: builder.queryParams,
    body: builder.body || undefined,
    environment_id: builder.environmentId,
  });

  /** In-place "Save" for an already-loaded request. Its collection/folder are left unchanged (both omitted from the patch). */
  const handleSaveInPlace = async () => {
    if (!loadedRequest) return;
    try {
      const updated = await updateSavedRequest.mutateAsync({
        id: loadedRequest.id,
        input: buildSaveInput(),
      });
      setLoadedRequest(updated);
      message.success('Request saved');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const openSaveModal = () => {
    if (loadedRequest) {
      // "Save as New" from an existing request: default to its own collection/folder.
      setSaveName(`${loadedRequest.name} (copy)`);
      setSaveCollectionId(loadedRequest.collection_id);
      setSaveFolderId(loadedRequest.folder_id ?? undefined);
    } else {
      setSaveName('');
      setSaveCollectionId(createTarget?.collectionId ?? collections[0]?.id);
      setSaveFolderId(createTarget?.folderId);
    }
    setSaveModalOpen(true);
  };

  const handleSaveConfirm = async () => {
    if (!saveName.trim()) {
      message.warning('Enter a name');
      return;
    }
    if (!saveCollectionId) {
      message.warning('Choose a collection');
      return;
    }
    try {
      const created = await createSavedRequest.mutateAsync({
        name: saveName.trim(),
        collection_id: saveCollectionId,
        folder_id: saveFolderId,
        ...buildSaveInput(),
      });
      setLoadedRequest(created);
      setCreateTarget(null);
      setSaveModalOpen(false);
      message.success('Request saved');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const foldersForSaveCollection = useMemo(
    () => collections.find((c) => c.id === saveCollectionId)?.folders ?? [],
    [collections, saveCollectionId],
  );

  // --- Collection / folder node actions ---

  const openRenameCollection = (id: string, currentName: string) => {
    setNodeModal({ mode: 'rename-collection', id });
    setNodeModalName(currentName);
  };
  const openRenameFolder = (id: string, collectionId: string, currentName: string) => {
    setNodeModal({ mode: 'rename-folder', id, collectionId });
    setNodeModalName(currentName);
  };
  const openNewCollection = () => {
    setNodeModal({ mode: 'new-collection' });
    setNodeModalName('');
  };
  const openNewFolder = (collectionId: string) => {
    setNodeModal({ mode: 'new-folder', collectionId });
    setNodeModalName('');
  };

  const nodeModalTitle = (() => {
    if (!nodeModal) return '';
    switch (nodeModal.mode) {
      case 'new-collection':
        return 'New Collection';
      case 'new-folder':
        return 'New Folder';
      case 'rename-collection':
        return 'Rename Collection';
      case 'rename-folder':
        return 'Rename Folder';
    }
  })();

  const nodeModalPending =
    createCollection.isPending ||
    createFolder.isPending ||
    updateCollection.isPending ||
    updateFolder.isPending;

  const handleNodeModalConfirm = async () => {
    if (!nodeModal) return;
    const name = nodeModalName.trim();
    if (!name) {
      message.warning('Enter a name');
      return;
    }
    try {
      switch (nodeModal.mode) {
        case 'new-collection':
          await createCollection.mutateAsync({ name });
          message.success('Collection created');
          break;
        case 'new-folder':
          await createFolder.mutateAsync({ collectionId: nodeModal.collectionId, input: { name } });
          message.success('Folder created');
          break;
        case 'rename-collection':
          await updateCollection.mutateAsync({ id: nodeModal.id, input: { name } });
          message.success('Collection renamed');
          break;
        case 'rename-folder':
          await updateFolder.mutateAsync({
            collectionId: nodeModal.collectionId,
            folderId: nodeModal.id,
            input: { name },
          });
          message.success('Folder renamed');
          break;
      }
      setNodeModal(null);
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleDeleteCollection = async (id: string) => {
    try {
      await deleteCollection.mutateAsync(id);
      message.success('Collection deleted');
      if (loadedRequest?.collection_id === id) handleNewRequest();
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleDeleteFolder = async (collectionId: string, folderId: string) => {
    try {
      await deleteFolder.mutateAsync({ collectionId, folderId });
      message.success('Folder deleted — its requests were moved to the collection top level');
      if (loadedRequest?.folder_id === folderId) {
        setLoadedRequest({ ...loadedRequest, folder_id: null });
      }
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  // --- Tree data ---

  // Rebuilt each render from `collections` (cheap: a handful of nodes) — not memoized, since the
  // node action handlers it closes over aren't stable callbacks and memoizing would just recompute
  // every render anyway while adding a misleading dependency array.
  const treeData: TreeDataNode[] = (() => {
    const buildRequestNode = (req: { id: string; name: string; method: string }): TreeDataNode => ({
      key: `request:${req.id}`,
      isLeaf: true,
      title: (
        <TreeNodeRow
          testId={`request-node-${req.id}`}
          actions={
            <Popconfirm
              title="Delete this request?"
              okText="Delete"
              okButtonProps={{ danger: true }}
              onConfirm={() => handleDeleteRequest(req.id)}
            >
              <span data-testid={`delete-request-button-${req.id}`}>
                <Button type="text" size="small" danger icon={<DeleteOutlined />} />
              </span>
            </Popconfirm>
          }
        >
          <Text
            style={{
              color: methodColor(req.method),
              fontWeight: 700,
              fontSize: 11,
              minWidth: 42,
              display: 'inline-block',
            }}
          >
            {req.method}
          </Text>
          <Text ellipsis style={{ maxWidth: 120 }}>
            {req.name}
          </Text>
        </TreeNodeRow>
      ),
    });

    const buildFolderNode = (
      collectionId: string,
      folder: ApiCollectionTreeNode['folders'][number],
    ): TreeDataNode => ({
      key: `folder:${folder.id}`,
      children: folder.requests.map(buildRequestNode),
      title: (
        <TreeNodeRow
          testId={`folder-node-${folder.id}`}
          actions={
            <>
              <span data-testid={`add-request-button-${folder.id}`}>
                <Button
                  type="text"
                  size="small"
                  icon={<FileAddOutlined />}
                  title="Add request"
                  onClick={() => handleStartNewRequestIn({ collectionId, folderId: folder.id })}
                />
              </span>
              <Button
                type="text"
                size="small"
                icon={<EditOutlined />}
                title="Rename folder"
                onClick={() => openRenameFolder(folder.id, collectionId, folder.name)}
              />
              <Popconfirm
                title="Delete this folder? Its requests will move to the collection's top level."
                okText="Delete"
                okButtonProps={{ danger: true }}
                onConfirm={() => handleDeleteFolder(collectionId, folder.id)}
              >
                <span data-testid={`delete-folder-button-${folder.id}`}>
                  <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                </span>
              </Popconfirm>
            </>
          }
        >
          <FolderOutlined style={{ color: '#d48806', fontSize: 13 }} />
          <Text strong ellipsis style={{ maxWidth: 122 }}>
            {folder.name}
          </Text>
        </TreeNodeRow>
      ),
    });

    return collections.map((coll) => ({
      key: `collection:${coll.id}`,
      children: [
        ...coll.folders.map((folder) => buildFolderNode(coll.id, folder)),
        ...coll.requests.map(buildRequestNode),
      ],
      title: (
        <TreeNodeRow
          testId={`collection-node-${coll.id}`}
          actions={
            <>
              <span data-testid={`add-folder-button-${coll.id}`}>
                <Button
                  type="text"
                  size="small"
                  icon={<FolderAddOutlined />}
                  title="Add folder"
                  onClick={() => openNewFolder(coll.id)}
                />
              </span>
              <span data-testid={`add-request-button-${coll.id}`}>
                <Button
                  type="text"
                  size="small"
                  icon={<FileAddOutlined />}
                  title="Add request"
                  onClick={() => handleStartNewRequestIn({ collectionId: coll.id })}
                />
              </span>
              <Button
                type="text"
                size="small"
                icon={<EditOutlined />}
                title="Rename collection"
                onClick={() => openRenameCollection(coll.id, coll.name)}
              />
              <Popconfirm
                title="Delete this collection? Its folders and requests will be deleted too."
                okText="Delete"
                okButtonProps={{ danger: true }}
                onConfirm={() => handleDeleteCollection(coll.id)}
              >
                <span data-testid={`delete-collection-button-${coll.id}`}>
                  <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                </span>
              </Popconfirm>
            </>
          }
        >
          <ApiOutlined style={{ color: '#1677ff', fontSize: 13 }} />
          <Text strong ellipsis style={{ maxWidth: 112 }}>
            {coll.name}
          </Text>
        </TreeNodeRow>
      ),
    }));
  })();

  const headerEntries = Object.entries(response?.headers ?? {});
  // "Preview" renders HTML responses in a sandboxed iframe; anything else (JSON, plain text, etc.)
  // falls back to the same pretty-printed/highlighted view as the Body tab.
  const responseContentType =
    headerEntries.find(([k]) => k.toLowerCase() === 'content-type')?.[1] ?? '';
  const isHtmlResponse = /text\/html/i.test(responseContentType);

  return (
    <div>
      {/* Hover-reveal the per-node action icons only when the row (or an already-open Popconfirm on it) is hovered. */}
      <style>{`
        .api-tree-node-actions { opacity: 0; transition: opacity 0.15s ease; }
        .api-tree-node:hover .api-tree-node-actions { opacity: 1; }
      `}</style>

      <Title level={3} style={{ marginBottom: 16 }}>
        API Performer
      </Title>

      <Row gutter={16}>
        <Col span={7}>
          <Card
            title="Collections"
            size="small"
            styles={{ body: { maxHeight: 640, overflow: 'auto' } }}
            extra={
              <span data-testid="new-collection-button">
                <Button size="small" icon={<PlusOutlined />} onClick={openNewCollection}>
                  New Collection
                </Button>
              </span>
            }
          >
            {!treeLoading && collections.length === 0 ? (
              <Empty
                description="No collections yet. Create one to start saving requests."
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              >
                <Button type="primary" icon={<PlusOutlined />} onClick={openNewCollection}>
                  Create your first collection
                </Button>
              </Empty>
            ) : (
              <Tree
                treeData={treeData}
                selectable
                blockNode
                expandedKeys={expandedKeys}
                onExpand={(keys) => setExpandedKeys(keys as string[])}
                onSelect={(_keys, info) => {
                  const key = String(info.node.key);
                  if (key.startsWith('request:')) {
                    handleSelectRequestNode(key.slice('request:'.length));
                  }
                }}
              />
            )}
          </Card>
        </Col>

        <Col span={17}>
          <Card title="Request Builder" size="small" style={{ marginBottom: 16 }}>
            {/* Postman-style breadcrumb: protocol icon + Collection > Folder > Request path of the
                currently-loaded saved request. Unsaved/ad-hoc requests show a plain "Unsaved Request"
                label instead of a path, since there's nowhere to point the breadcrumb yet. */}
            <div
              data-testid="request-breadcrumb"
              style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}
            >
              <GlobalOutlined style={{ color: '#8c8c8c' }} />
              {requestPath ? (
                <Breadcrumb
                  items={[
                    { title: requestPath.collectionName },
                    ...(requestPath.folderName ? [{ title: requestPath.folderName }] : []),
                    {
                      title: (
                        <Space size={6}>
                          <Text style={{ color: methodColor(builder.method), fontWeight: 700, fontSize: 12 }}>
                            {builder.method}
                          </Text>
                          <Text strong>{requestPath.requestName}</Text>
                        </Space>
                      ),
                    },
                  ]}
                />
              ) : (
                <Text type="secondary" italic>
                  Unsaved Request
                </Text>
              )}
            </div>

            <Space.Compact style={{ width: '100%', marginBottom: 4 }}>
              <Select
                value={builder.method}
                style={{ width: 130 }}
                options={HTTP_METHODS.map((m) => ({
                  value: m,
                  label: (
                    <Tag color={HTTP_METHOD_COLORS[m]} style={{ marginRight: 0 }}>
                      {m}
                    </Tag>
                  ),
                }))}
                onChange={(method) => setBuilder((b) => ({ ...b, method }))}
                data-testid="request-method-select"
              />
              <Input
                placeholder="https://api.example.com/resource"
                value={builder.url}
                onChange={(e) => setBuilder((b) => ({ ...b, url: e.target.value }))}
                data-testid="request-url-input"
              />
              <span data-testid="send-request-button">
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  loading={executeAdHoc.isPending}
                  onClick={handleSend}
                >
                  Send
                </Button>
              </span>
            </Space.Compact>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Use {'{{base_url}}'} or {'{{VARIABLE_NAME}}'} to reference the selected environment.
            </Text>

            <div style={{ marginTop: 12, marginBottom: 12 }}>
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Text strong>Environment</Text>
                <Select
                  allowClear
                  placeholder="No environment"
                  style={{ width: 280 }}
                  loading={environmentsLoading}
                  value={builder.environmentId}
                  options={(environments ?? []).map((e) => ({ value: e.id, label: e.name }))}
                  onChange={(environmentId) => setBuilder((b) => ({ ...b, environmentId }))}
                  data-testid="request-environment-select"
                />
              </Space>
            </div>

            <Tabs
              items={[
                {
                  key: 'headers',
                  label: 'Headers',
                  children: (
                    <KeyValueListEditor
                      value={builder.headers}
                      onChange={(headers) => setBuilder((b) => ({ ...b, headers }))}
                    />
                  ),
                },
                {
                  key: 'query',
                  label: 'Query Params',
                  children: (
                    <KeyValueListEditor
                      value={builder.queryParams}
                      onChange={(queryParams) => setBuilder((b) => ({ ...b, queryParams }))}
                    />
                  ),
                },
                {
                  key: 'body',
                  label: 'Body',
                  children: (
                    <div>
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          marginBottom: 8,
                        }}
                      >
                        <Radio.Group
                          size="small"
                          value={builder.bodyMode}
                          onChange={(e) => setBuilder((b) => ({ ...b, bodyMode: e.target.value }))}
                          optionType="button"
                          buttonStyle="solid"
                          data-testid="request-body-mode"
                          options={[
                            { label: 'raw', value: 'raw' },
                            { label: 'JSON', value: 'json' },
                            { label: 'GraphQL', value: 'graphql' },
                          ]}
                        />
                        <Button
                          size="small"
                          icon={<FormatPainterOutlined />}
                          onClick={handleBeautifyBody}
                          data-testid="beautify-body-button"
                        >
                          Beautify
                        </Button>
                      </div>
                      <Input.TextArea
                        value={builder.body}
                        onChange={(e) => setBuilder((b) => ({ ...b, body: e.target.value }))}
                        autoSize={{ minRows: 6, maxRows: 16 }}
                        placeholder={
                          builder.bodyMode === 'graphql'
                            ? 'query { field { subField } }'
                            : 'Request body (raw)'
                        }
                        style={{ fontFamily: 'monospace', fontSize: 12 }}
                        data-testid="request-body-textarea"
                      />
                    </div>
                  ),
                },
              ]}
            />

            <Space style={{ marginTop: 12 }}>
              {loadedRequest ? (
                <span data-testid="save-request-button">
                  <Button loading={updateSavedRequest.isPending} onClick={handleSaveInPlace}>
                    Save
                  </Button>
                </span>
              ) : null}
              <span data-testid={loadedRequest ? 'save-as-new-request-button' : 'save-request-button'}>
                <Button onClick={openSaveModal}>{loadedRequest ? 'Save as New' : 'Save'}</Button>
              </span>
              {(loadedRequest || createTarget) && (
                <Button type="link" onClick={handleNewRequest}>
                  New Request
                </Button>
              )}
            </Space>

            {loadedRequest && (
              <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
                Editing saved request: <Text strong>{loadedRequest.name}</Text>
              </Text>
            )}
            {!loadedRequest && createTarget && (
              <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
                New request will be saved into{' '}
                {createTarget.folderId
                  ? collections
                      .find((c) => c.id === createTarget.collectionId)
                      ?.folders.find((f) => f.id === createTarget.folderId)?.name
                  : collections.find((c) => c.id === createTarget.collectionId)?.name}
                .
              </Text>
            )}
          </Card>

          <Card title="Response" size="small">
            {(executeAdHoc.isPending || loadingRequestId) && <Text type="secondary">Loading…</Text>}
            {!executeAdHoc.isPending && !loadingRequestId && response && (
              <>
                {response.error ? (
                  <Alert type="error" showIcon message="Request failed" description={response.error} />
                ) : (
                  <>
                    <Space style={{ marginBottom: 8 }} align="center">
                      <span data-testid="response-status">
                        <Tag color={statusTagColor(response.status_code)}>
                          {response.status_code ?? 'No response'}
                        </Tag>
                      </span>
                      <Text type="secondary">{response.duration_ms} ms</Text>
                    </Space>
                    {headerEntries.length > 0 && (
                      <Collapse
                        size="small"
                        style={{ marginBottom: 8 }}
                        items={[
                          {
                            key: 'headers',
                            label: 'Response Headers',
                            children: (
                              <div data-testid="response-headers">
                                <JsonOrPlainView
                                  text={JSON.stringify(Object.fromEntries(headerEntries))}
                                />
                              </div>
                            ),
                          },
                        ]}
                      />
                    )}
                    <Tabs
                      size="small"
                      items={[
                        {
                          key: 'body',
                          label: 'Body',
                          children: (
                            <div data-testid="response-body">
                              <JsonOrPlainView text={response.body} emptyText="No response body" />
                            </div>
                          ),
                        },
                        {
                          key: 'preview',
                          label: (
                            <span>
                              <EyeOutlined /> Preview
                            </span>
                          ),
                          children: isHtmlResponse ? (
                            <iframe
                              title="Response preview"
                              // Sandboxed with no allowed capabilities (no scripts, no same-origin,
                              // no forms) — a response body is untrusted content, this is a preview
                              // pane, not a script execution surface.
                              sandbox=""
                              srcDoc={response.body}
                              data-testid="response-preview-iframe"
                              style={{
                                width: '100%',
                                height: 400,
                                border: '1px solid #f0f0f0',
                                borderRadius: 4,
                                background: '#fff',
                              }}
                            />
                          ) : (
                            <div data-testid="response-preview-json">
                              <JsonOrPlainView text={response.body} emptyText="No response body" />
                            </div>
                          ),
                        },
                      ]}
                    />
                  </>
                )}
              </>
            )}
            {!executeAdHoc.isPending && !loadingRequestId && !response && (
              <Text type="secondary">Send a request to see the response here.</Text>
            )}
          </Card>
        </Col>
      </Row>

      <Modal
        title={loadedRequest ? 'Save as New Request' : 'Save Request'}
        open={saveModalOpen}
        onOk={handleSaveConfirm}
        onCancel={() => setSaveModalOpen(false)}
        confirmLoading={createSavedRequest.isPending}
        okText="Save"
        destroyOnHidden
      >
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Input
            placeholder="Request name"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            data-testid="save-request-name-input"
          />
          <div>
            <Text style={{ display: 'block', marginBottom: 4 }}>Collection</Text>
            <Select
              style={{ width: '100%' }}
              placeholder="Choose a collection"
              value={saveCollectionId}
              options={collections.map((c) => ({ value: c.id, label: c.name }))}
              onChange={(collectionId) => {
                setSaveCollectionId(collectionId);
                setSaveFolderId(undefined);
              }}
              data-testid="save-collection-select"
            />
          </div>
          <div>
            <Text style={{ display: 'block', marginBottom: 4 }}>Folder (optional)</Text>
            <Select
              allowClear
              style={{ width: '100%' }}
              placeholder="Top level of the collection"
              value={saveFolderId}
              disabled={!saveCollectionId}
              options={foldersForSaveCollection.map((f) => ({ value: f.id, label: f.name }))}
              onChange={(folderId) => setSaveFolderId(folderId)}
              data-testid="save-folder-select"
            />
          </div>
        </Space>
      </Modal>

      <Modal
        title={nodeModalTitle}
        open={nodeModal !== null}
        onOk={handleNodeModalConfirm}
        onCancel={() => setNodeModal(null)}
        confirmLoading={nodeModalPending}
        okText={nodeModal?.mode.startsWith('rename') ? 'Rename' : 'Create'}
        destroyOnHidden
      >
        <Input
          placeholder="Name"
          value={nodeModalName}
          onChange={(e) => setNodeModalName(e.target.value)}
          onPressEnter={handleNodeModalConfirm}
          data-testid="node-modal-name-input"
        />
      </Modal>
    </div>
  );
}
