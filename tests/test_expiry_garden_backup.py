import os
import sys
import sqlite3
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Food_manager import InventoryManager
import backup_scheduler


@pytest.fixture
def manager(tmp_path):
    db = str(tmp_path / "test.db")
    return InventoryManager(db_filepath=db)


def _make_product(manager, name="Tomatoes"):
    manager.add_category("Produce")
    cat_id = next(c["id"] for c in manager.get_all_categories_with_subcategories()
                  if c["name"] == "Produce")
    manager.create_product(name=name, category_id=cat_id, subcategory_id=None,
                           unit_of_measure="Eaches", default_expiry_days=7)
    for p in manager.get_all_products_export():
        if p["name"] == name:
            return p["id"]
    raise AssertionError("product not created")


def _insert_batch(manager, product_id, name, qty, expiry):
    with manager._get_db_connection() as conn:
        conn.execute(
            "INSERT INTO inventory_items (product_id, name, quantity, purchase_date, expiry_date)"
            " VALUES (?, ?, ?, ?, ?)",
            (product_id, name, str(qty), date.today().isoformat(), expiry.isoformat()),
        )
        conn.commit()


class TestExpiringBatches:
    def test_flags_expired_and_expiring(self, manager):
        pid = _make_product(manager)
        today = date.today()
        _insert_batch(manager, pid, "Tomatoes", 3, today - timedelta(days=2))  # expired
        _insert_batch(manager, pid, "Tomatoes", 2, today + timedelta(days=3))  # expiring
        _insert_batch(manager, pid, "Tomatoes", 5, today + timedelta(days=30))  # fine

        rows = manager.get_expiring_batches(days_ahead=7)
        assert len(rows) == 2
        days = sorted(r["days_until_expiry"] for r in rows)
        assert days == [-2, 3]

    def test_zero_quantity_batches_ignored(self, manager):
        pid = _make_product(manager)
        _insert_batch(manager, pid, "Tomatoes", 0, date.today() + timedelta(days=1))
        assert manager.get_expiring_batches(days_ahead=7) == []

    def test_ordered_soonest_first(self, manager):
        pid = _make_product(manager)
        today = date.today()
        _insert_batch(manager, pid, "Tomatoes", 1, today + timedelta(days=5))
        _insert_batch(manager, pid, "Tomatoes", 1, today + timedelta(days=1))
        rows = manager.get_expiring_batches(days_ahead=7)
        assert [r["days_until_expiry"] for r in rows] == [1, 5]


class TestGardenSupply:
    def test_active_harvest_window_counts(self, manager):
        pid = _make_product(manager)
        today = date.today()
        # Planted 60 days ago, 50 days to harvest, 20-day window, 40 total yield.
        # Harvest window started 10 days ago and runs 10 more days: 2/day.
        manager.add_production_item(
            name="Tomato Plant", associated_product_id=pid,
            plant_date_str=(today - timedelta(days=60)).isoformat(),
            status="Growing", time_to_harvest_days=50,
            expected_harvest_period_days=20, expected_yield_total=40,
        )
        supply = manager.get_expected_garden_supply(pid, projection_days=7)
        assert supply["total"] == pytest.approx(14.0)  # 2/day * 7 days
        assert len(supply["sources"]) == 1

    def test_future_window_outside_horizon_is_zero(self, manager):
        pid = _make_product(manager)
        manager.add_production_item(
            name="Tomato Plant", associated_product_id=pid,
            plant_date_str=date.today().isoformat(),
            status="Growing", time_to_harvest_days=60,
            expected_harvest_period_days=30, expected_yield_total=10,
        )
        assert manager.get_expected_garden_supply(pid, projection_days=7)["total"] == 0.0

    def test_finished_items_ignored(self, manager):
        pid = _make_product(manager)
        manager.add_production_item(
            name="Tomato Plant", associated_product_id=pid,
            plant_date_str=(date.today() - timedelta(days=60)).isoformat(),
            status="Finished", time_to_harvest_days=50,
            expected_harvest_period_days=20, expected_yield_total=40,
        )
        assert manager.get_expected_garden_supply(pid, projection_days=7)["total"] == 0.0

    def test_project_demand_includes_garden_fields(self, manager):
        pid = _make_product(manager)
        result = manager.project_demand(pid, projection_days=7)
        assert result["success"]
        assert "expected_garden_supply" in result
        assert "projected_need_after_garden" in result
        assert result["projected_need_after_garden"] <= result["projected_need"] or \
            result["projected_need_after_garden"] == 0.0


class TestBackupScheduler:
    def test_snapshot_and_prune(self, tmp_path):
        db = str(tmp_path / "src.db")
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.execute("INSERT INTO t VALUES ('pantry')")
        conn.commit()
        conn.close()

        bdir = str(tmp_path / "backups")
        dest = backup_scheduler._backup_once(db, bdir)
        check = sqlite3.connect(dest)
        assert check.execute("SELECT v FROM t").fetchone()[0] == "pantry"
        check.close()

        # Create extra fake snapshots and prune to 2
        for i in range(4):
            open(os.path.join(bdir, f"food_app_2020-01-0{i+1}_000000.db"), "w").close()
        backup_scheduler._prune(bdir, keep=2)
        remaining = [f for f in os.listdir(bdir) if f.endswith(".db")]
        assert len(remaining) == 2

    def test_disabled_without_env(self, monkeypatch):
        monkeypatch.delenv("PIM_BACKUP_DIR", raising=False)
        assert backup_scheduler.start_backup_scheduler("/tmp/x.db") is None
