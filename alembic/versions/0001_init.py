
from alembic import op
import sqlalchemy as sa

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("username", sa.String(150), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "rags",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("creator_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_rags_org", "rags", ["org_id"])
    op.create_index("ix_rags_org_name", "rags", ["org_id", "name"], unique=True)

    op.create_table(
        "rag_members",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("rag_id", sa.Integer, sa.ForeignKey("rags.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.Enum("admin", "user", name="roleenum"), nullable=False, server_default="user"),
        sa.Column("approved", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("joined_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_rag_members_unique", "rag_members", ["rag_id", "user_id"], unique=True)

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("rag_id", sa.Integer, sa.ForeignKey("rags.id"), nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("path", sa.String(1024), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("uploaded_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_documents_rag", "documents", ["rag_id"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("doc_id", sa.Integer, sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
    )
    op.create_index("ix_chunk_doc", "chunks", ["doc_id"])
    op.create_index("ix_chunk_doc_idx", "chunks", ["doc_id", "chunk_index"], unique=True)

    op.create_table(
        "discussions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("rag_id", sa.Integer, sa.ForeignKey("rags.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_disc_rag", "discussions", ["rag_id"])
    op.create_index("ix_disc_user", "discussions", ["user_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("discussion_id", sa.Integer, sa.ForeignKey("discussions.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_msg_disc", "messages", ["discussion_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("details_json", sa.JSON, nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("ts", sa.DateTime, nullable=False),
    )
    op.create_index("ix_audit_user", "audit_logs", ["user_id"])

def downgrade():
    op.drop_table("audit_logs")
    op.drop_index("ix_msg_disc", table_name="messages"); op.drop_table("messages")
    op.drop_index("ix_disc_user", table_name="discussions"); op.drop_index("ix_disc_rag", table_name="discussions"); op.drop_table("discussions")
    op.drop_index("ix_chunk_doc_idx", table_name="chunks"); op.drop_index("ix_chunk_doc", table_name="chunks"); op.drop_table("chunks")
    op.drop_index("ix_documents_rag", table_name="documents"); op.drop_table("documents")
    op.drop_index("ix_rag_members_unique", table_name="rag_members"); op.drop_table("rag_members")
    op.drop_index("ix_rags_org_name", table_name="rags"); op.drop_index("ix_rags_org", table_name="rags"); op.drop_table("rags")
    op.drop_index("ix_users_username", table_name="users"); op.drop_index("ix_users_email", table_name="users"); op.drop_table("users")
    op.drop_table("organizations")
