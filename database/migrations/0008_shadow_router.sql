-- Shadow router examples: local training/evaluation corpus. The shadow router never controls live routing.
CREATE TABLE IF NOT EXISTS shadow_router_examples (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    thread_id TEXT,
    run_id TEXT,
    request_text TEXT NOT NULL,
    primary_route TEXT NOT NULL,
    shadow_route TEXT,
    agreement BOOLEAN,
    shadow_model TEXT,
    shadow_confidence DOUBLE PRECISION,
    shadow_error TEXT
);
CREATE INDEX IF NOT EXISTS shadow_router_examples_created
    ON shadow_router_examples(created_at DESC);
CREATE INDEX IF NOT EXISTS shadow_router_examples_routes
    ON shadow_router_examples(primary_route, shadow_route);
