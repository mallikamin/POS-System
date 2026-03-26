"""
Seed script for Italian Restaurant (Cosa Nostra style)
Loads 137 menu items (208 after price splits) from Restaurant Menu.xlsm

Usage:
    python -m app.scripts.seed_italian_restaurant
"""
import asyncio
import openpyxl
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_engine, AsyncSessionLocal
from app.models import Tenant, Category, MenuItem


async def seed_italian_restaurant():
    """Seed Italian restaurant menu from Excel file"""

    async with AsyncSessionLocal() as db:
        # Get or create tenant
        result = await db.execute(select(Tenant).where(Tenant.slug == "demo"))
        tenant = result.scalar_one_or_none()

        if not tenant:
            print("❌ Demo tenant not found. Run seed.py first.")
            return

        tenant_id = tenant.id
        print(f"✅ Using tenant: {tenant.name} ({tenant_id})")

        # Parse Excel file
        excel_path = Path(__file__).parent.parent.parent.parent / "docs" / "Restaurant Menu.xlsm"
        if not excel_path.exists():
            print(f"❌ Excel file not found: {excel_path}")
            return

        print(f"📄 Reading Excel file: {excel_path}")
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        ws = wb['Sheet1']

        # Parse data
        category_names = set()
        items_data = []

        for row in ws.iter_rows(min_row=2, max_row=138, values_only=True):
            item_name = row[1]
            category_name = row[2]
            base_price = row[3]

            if not item_name or not category_name:
                continue

            category_names.add(category_name)

            # Check for price splits (columns 4-11: label, price, label, price, ...)
            splits = []
            for i in range(4, 12, 2):
                split_label = row[i]
                split_price = row[i+1]
                if split_label and split_price:
                    try:
                        splits.append({
                            'label': str(split_label).strip(),
                            'price': int(split_price)
                        })
                    except (ValueError, TypeError):
                        pass

            if splits:
                # Create separate items for each split
                for split in splits:
                    items_data.append({
                        'name': f"{item_name} ({split['label']})",
                        'category': category_name,
                        'price_paisa': split['price'] * 100  # Convert to paisa
                    })
            elif base_price:
                try:
                    items_data.append({
                        'name': item_name,
                        'category': category_name,
                        'price_paisa': int(base_price) * 100  # Convert to paisa
                    })
                except (ValueError, TypeError):
                    pass

        print(f"📊 Parsed: {len(category_names)} categories, {len(items_data)} items (after splits)")

        # Delete existing menu items and categories
        print("🗑️  Deleting existing menu items...")
        await db.execute(
            select(MenuItem).where(MenuItem.tenant_id == tenant_id)
        )
        result = await db.execute(select(MenuItem).where(MenuItem.tenant_id == tenant_id))
        existing_items = result.scalars().all()
        for item in existing_items:
            await db.delete(item)

        print("🗑️  Deleting existing categories...")
        result = await db.execute(select(Category).where(Category.tenant_id == tenant_id))
        existing_categories = result.scalars().all()
        for cat in existing_categories:
            await db.delete(cat)

        await db.commit()

        # Create categories
        print(f"📁 Creating {len(category_names)} categories...")
        category_map = {}

        for i, cat_name in enumerate(sorted(category_names), start=1):
            category = Category(
                tenant_id=tenant_id,
                name=cat_name,
                slug=cat_name.lower().replace(' ', '-').replace('&', 'and'),
                description=f"{cat_name} items",
                display_order=i,
                is_active=True
            )
            db.add(category)
            await db.flush()
            category_map[cat_name] = category.id
            print(f"  ✓ {cat_name}")

        await db.commit()

        # Create menu items
        print(f"🍽️  Creating {len(items_data)} menu items...")
        created_count = 0

        for item_data in items_data:
            category_id = category_map.get(item_data['category'])
            if not category_id:
                print(f"  ⚠️  Skipping {item_data['name']} - category not found")
                continue

            menu_item = MenuItem(
                tenant_id=tenant_id,
                category_id=category_id,
                name=item_data['name'],
                description=f"{item_data['name']} from our Italian menu",
                price_paisa=item_data['price_paisa'],
                is_active=True,
                is_available=True,
                image_url=None  # No images in Excel file
            )
            db.add(menu_item)
            created_count += 1

            if created_count % 50 == 0:
                print(f"  ✓ {created_count} items created...")

        await db.commit()
        print(f"✅ Successfully created {created_count} menu items")

        # Summary
        print("\n" + "="*60)
        print("SEED COMPLETE - Italian Restaurant Menu")
        print("="*60)
        print(f"Tenant: {tenant.name}")
        print(f"Categories: {len(category_names)}")
        print(f"Menu Items: {created_count}")
        print(f"\nCategory breakdown:")
        for cat_name in sorted(category_names):
            count = sum(1 for item in items_data if item['category'] == cat_name)
            print(f"  {cat_name}: {count} items")
        print("="*60)


async def main():
    print("🚀 Starting Italian Restaurant seed...")
    print()

    async with async_engine.begin() as conn:
        await conn.run_sync(lambda _: None)  # Verify connection

    await seed_italian_restaurant()

    await async_engine.dispose()
    print("\n✅ Seed complete!")


if __name__ == "__main__":
    asyncio.run(main())
