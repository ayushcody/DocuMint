-- PostgreSQL row-level security bootstrap.
-- Every document-bearing table has workspace_id and must enforce this policy.

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE parse_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE parse_blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE extraction_schemas ENABLE ROW LEVEL SECURITY;
ALTER TABLE extraction_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE index_collections ENABLE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation_documents ON documents
  USING (workspace_id = current_setting('app.workspace_id')::uuid);

CREATE POLICY workspace_isolation_parse_runs ON parse_runs
  USING (workspace_id = current_setting('app.workspace_id')::uuid);

CREATE POLICY workspace_isolation_parse_blocks ON parse_blocks
  USING (workspace_id = current_setting('app.workspace_id')::uuid);

CREATE POLICY workspace_isolation_extraction_schemas ON extraction_schemas
  USING (workspace_id = current_setting('app.workspace_id')::uuid);

CREATE POLICY workspace_isolation_extraction_runs ON extraction_runs
  USING (workspace_id = current_setting('app.workspace_id')::uuid);

CREATE POLICY workspace_isolation_index_collections ON index_collections
  USING (workspace_id = current_setting('app.workspace_id')::uuid);
