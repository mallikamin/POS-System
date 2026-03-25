"""add_bom_inventory_tables

Revision ID: m9n0o1p2q3r4
Revises: l8m9n0o1p2q3
Create Date: 2026-03-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'm9n0o1p2q3r4'
down_revision = 'bb5abf47cc8b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ingredients table
    op.create_table(
        'ingredients',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False, server_default='General'),
        sa.Column('unit', sa.String(length=50), nullable=False),
        sa.Column('cost_per_unit', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'),
        sa.Column('supplier_name', sa.String(length=200), nullable=True),
        sa.Column('supplier_contact', sa.String(length=100), nullable=True),
        sa.Column('current_stock', sa.Numeric(precision=12, scale=3), nullable=False, server_default='0'),
        sa.Column('reorder_point', sa.Numeric(precision=12, scale=3), nullable=False, server_default='0'),
        sa.Column('reorder_quantity', sa.Numeric(precision=12, scale=3), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_ingredient_tenant_name')
    )
    op.create_index('ix_ingredient_tenant_category', 'ingredients', ['tenant_id', 'category'])
    op.create_index('ix_ingredient_tenant_active', 'ingredients', ['tenant_id', 'is_active'])
    op.create_index(op.f('ix_ingredients_tenant_id'), 'ingredients', ['tenant_id'])

    # Create recipes table
    op.create_table(
        'recipes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('yield_servings', sa.Numeric(precision=8, scale=2), nullable=False, server_default='1'),
        sa.Column('prep_time_minutes', sa.Integer(), nullable=True),
        sa.Column('cook_time_minutes', sa.Integer(), nullable=True),
        sa.Column('total_ingredient_cost', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'),
        sa.Column('cost_per_serving', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'menu_item_id', name='uq_recipe_tenant_item')
    )
    op.create_index('ix_recipe_tenant_active', 'recipes', ['tenant_id', 'is_active'])
    op.create_index(op.f('ix_recipes_tenant_id'), 'recipes', ['tenant_id'])

    # Create recipe_items table
    op.create_table(
        'recipe_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('recipe_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=False),
        sa.Column('waste_factor', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0'),
        sa.Column('cost_per_unit_snapshot', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'),
        sa.Column('total_cost', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recipe_id', 'ingredient_id', name='uq_recipeitem_recipe_ingredient')
    )
    op.create_index('ix_recipeitem_recipe', 'recipe_items', ['recipe_id'])
    op.create_index(op.f('ix_recipe_items_tenant_id'), 'recipe_items', ['tenant_id'])

    # Create inventory_transactions table
    op.create_table(
        'inventory_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transaction_type', sa.String(length=50), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=False),
        sa.Column('unit_cost', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'),
        sa.Column('total_cost', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'),
        sa.Column('balance_after', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('transaction_date', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('performed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reference_number', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['ingredient_id'], ['ingredients.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['performed_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_invtx_ingredient', 'inventory_transactions', ['ingredient_id'])
    op.create_index('ix_invtx_tenant_date', 'inventory_transactions', ['tenant_id', 'transaction_date'])
    op.create_index('ix_invtx_type', 'inventory_transactions', ['transaction_type'])
    op.create_index(op.f('ix_inventory_transactions_tenant_id'), 'inventory_transactions', ['tenant_id'])

    # Create stock_counts table
    op.create_table(
        'stock_counts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('count_date', sa.Date(), nullable=False),
        sa.Column('count_number', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
        sa.Column('counted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_variance_cost', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('total_items_counted', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('items_with_variance', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('count_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['counted_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_stockcount_tenant_date', 'stock_counts', ['tenant_id', 'count_date'])
    op.create_index('ix_stockcount_tenant_status', 'stock_counts', ['tenant_id', 'status'])
    op.create_index(op.f('ix_stock_counts_tenant_id'), 'stock_counts', ['tenant_id'])


def downgrade() -> None:
    op.drop_table('stock_counts')
    op.drop_table('inventory_transactions')
    op.drop_table('recipe_items')
    op.drop_table('recipes')
    op.drop_table('ingredients')
