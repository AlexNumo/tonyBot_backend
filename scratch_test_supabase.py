import asyncio
import database

async def test():
    print("=== Supabase Connection Test ===")
    try:
        # 1. Fetch packages
        packages = await database.get_packages()
        print(f"Connection successful! Found {len(packages)} packages in DB:")
        for p in packages:
            print(f"  - {p['id']}: {p['name']} (Price: {p['price']}, Places: {p['available_places']})")
            
        # 2. Add a dummy test user
        test_user_id = 999999
        print(f"\nTrying to insert/upsert test user (id={test_user_id})...")
        await database.add_user(test_user_id, "antigravity_test_user")
        print("User insertion completed successfully!")

        # 3. Add a dummy lead
        print(f"\nTrying to insert test lead for user {test_user_id}...")
        await database.save_lead(test_user_id, "VIP (Індивідуально) - 400€")
        print("Lead insertion completed successfully! RLS Bypassed.")
        
    except Exception as e:
        print("\n❌ Error during execution:")
        print(e)

if __name__ == "__main__":
    asyncio.run(test())
