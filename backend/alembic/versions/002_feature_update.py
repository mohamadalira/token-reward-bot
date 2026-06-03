"""Feature update: shop categories, sponsor channel description, product category_id."""

from alembic import op
import sqlalchemy as sa


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_token_cost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_shop_categories_slug", "shop_categories", ["slug"], unique=True)

    op.add_column("config_products", sa.Column("category_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_config_products_category_id",
        "config_products",
        "shop_categories",
        ["category_id"],
        ["id"],
    )
    op.create_index("ix_config_products_category_id", "config_products", ["category_id"])

    op.add_column("sponsor_channels", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sponsor_channels", "description")
    op.drop_index("ix_config_products_category_id", "config_products")
    op.drop_constraint("fk_config_products_category_id", "config_products", type_="foreignkey")
    op.drop_column("config_products", "category_id")
    op.drop_index("ix_shop_categories_slug", "shop_categories")
    op.drop_table("shop_categories")
