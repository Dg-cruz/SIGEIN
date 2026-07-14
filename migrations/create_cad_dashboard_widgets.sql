-- Widgets personalizados do dashboard CAD
CREATE TABLE IF NOT EXISTS cad_dashboard_widgets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    widget_key VARCHAR(80) NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITHOUT TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_cad_dashboard_widgets_id ON cad_dashboard_widgets (id);
CREATE INDEX IF NOT EXISTS ix_cad_dashboard_widgets_user ON cad_dashboard_widgets (user_id);
