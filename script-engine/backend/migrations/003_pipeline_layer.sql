-- ============================================================
-- 第三轮重构: 编排层 — 数据库迁移
-- ============================================================

CREATE TABLE IF NOT EXISTS pipeline_state (
    project_id UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    template_name VARCHAR(50) NOT NULL,
    current_phase_index INTEGER DEFAULT 0,
    current_step_index INTEGER DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'not_started',
    result_data JSONB DEFAULT '{}',
    error_message TEXT DEFAULT '',
    task_results JSONB DEFAULT '[]',
    config JSONB DEFAULT '{}',
    run_id UUID,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_state_status ON pipeline_state(status);
