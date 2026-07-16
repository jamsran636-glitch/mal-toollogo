from __future__ import annotations

from datetime import date, datetime, timezone
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def uuid4() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('OWNER','HORSE_KEEPER','CATTLE_KEEPER','SHEEP_KEEPER')",
            name="ck_users_role",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(40), index=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    must_change_code: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    token_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped[User] = relationship()


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    __table_args__ = (
        Index("ix_login_attempt_lookup", "username", "ip_address", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(100), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    username: Mapped[str] = mapped_column(String(100), index=True)
    role: Mapped[str] = mapped_column(String(40), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    module: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    previous_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )


class HorseGroup(Base, TimestampMixin):
    __tablename__ = "horse_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    horses: Mapped[list[Horse]] = relationship(
        back_populates="group", foreign_keys="Horse.group_id"
    )


class Horse(Base, TimestampMixin):
    __tablename__ = "horses"
    __table_args__ = (
        CheckConstraint("sex IN ('MALE','FEMALE')", name="ck_horses_sex"),
        CheckConstraint(
            "male_status IS NULL OR male_status IN ('STALLION','GELDING','COLT')",
            name="ck_horses_male_status",
        ),
        CheckConstraint(
            "current_status IN ('ACTIVE','PREGNANT','ARCHIVED','DECEASED')",
            name="ck_horses_status",
        ),
        CheckConstraint(
            "birth_year >= 1980 AND birth_year <= 2100", name="ck_horses_birth_year"
        ),
        CheckConstraint(
            "mother_id IS NULL OR mother_id <> id", name="ck_horses_not_own_mother"
        ),
        CheckConstraint(
            "father_id IS NULL OR father_id <> id", name="ck_horses_not_own_father"
        ),
        CheckConstraint(
            "(current_status IN ('ARCHIVED','DECEASED')) = (archived_at IS NOT NULL)",
            name="ck_horses_archive_state",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    group_id: Mapped[str] = mapped_column(ForeignKey("horse_groups.id"), index=True)
    color: Mapped[str] = mapped_column(String(160), index=True)
    birth_year: Mapped[int] = mapped_column(Integer, index=True)
    sex: Mapped[str] = mapped_column(String(20), index=True)
    male_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )
    current_status: Mapped[str] = mapped_column(
        String(30), default="ACTIVE", index=True
    )
    mother_id: Mapped[str | None] = mapped_column(
        ForeignKey("horses.id"), nullable=True, index=True
    )
    father_id: Mapped[str | None] = mapped_column(
        ForeignKey("horses.id"), nullable=True, index=True
    )
    additional_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_image_id: Mapped[str | None] = mapped_column(
        ForeignKey("image_assets.id"), nullable=True
    )
    layout_image_id: Mapped[str | None] = mapped_column(
        ForeignKey("image_assets.id"), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archive_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    unnatural_loss: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    group: Mapped[HorseGroup] = relationship(
        back_populates="horses", foreign_keys=[group_id]
    )


class HorseGroupTransfer(Base):
    __tablename__ = "horse_group_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    horse_id: Mapped[str] = mapped_column(
        ForeignKey("horses.id", ondelete="CASCADE"), index=True
    )
    from_group_id: Mapped[str | None] = mapped_column(
        ForeignKey("horse_groups.id"), nullable=True
    )
    to_group_id: Mapped[str] = mapped_column(ForeignKey("horse_groups.id"))
    reason: Mapped[str] = mapped_column(Text)
    changed_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    changed_by_name: Mapped[str] = mapped_column(String(100))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )


class Cattle(Base, TimestampMixin):
    __tablename__ = "cattle"
    __table_args__ = (
        CheckConstraint("sex IN ('MALE','FEMALE')", name="ck_cattle_sex"),
        CheckConstraint(
            "current_status IN ('ACTIVE','ARCHIVED','DECEASED')",
            name="ck_cattle_status",
        ),
        CheckConstraint(
            "birth_year >= 1980 AND birth_year <= 2100", name="ck_cattle_birth_year"
        ),
        CheckConstraint("NOT is_bull OR sex = 'MALE'", name="ck_cattle_bull_male"),
        CheckConstraint(
            "mother_id IS NULL OR mother_id <> id", name="ck_cattle_not_own_mother"
        ),
        CheckConstraint(
            "(current_status IN ('ARCHIVED','DECEASED')) = (archived_at IS NOT NULL)",
            name="ck_cattle_archive_state",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    ear_tag: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    color: Mapped[str] = mapped_column(String(160), index=True)
    birth_year: Mapped[int] = mapped_column(Integer, index=True)
    sex: Mapped[str] = mapped_column(String(20), index=True)
    is_bull: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    current_status: Mapped[str] = mapped_column(
        String(30), default="ACTIVE", nullable=False, index=True
    )
    mother_id: Mapped[str | None] = mapped_column(
        ForeignKey("cattle.id"), nullable=True, index=True
    )
    additional_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_image_id: Mapped[str | None] = mapped_column(
        ForeignKey("image_assets.id"), nullable=True
    )
    layout_image_id: Mapped[str | None] = mapped_column(
        ForeignKey("image_assets.id"), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archive_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    unnatural_loss: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


NONNEGATIVE_COUNT_COLUMNS = (
    "sheep_male",
    "sheep_female",
    "goat_male",
    "goat_female",
    "male_lamb",
    "female_lamb",
    "male_kid",
    "female_kid",
    "hogget",
    "yearling_goat",
    "ram",
    "buck",
)


class SmallLivestockCount(Base, TimestampMixin):
    __tablename__ = "small_livestock_counts"
    __table_args__ = (
        CheckConstraint(
            "count_type IN ('FULL','EVENING')", name="ck_small_counts_type"
        ),
        *(
            CheckConstraint(
                f"{column} >= 0", name=f"ck_small_counts_{column}_nonnegative"
            )
            for column in NONNEGATIVE_COUNT_COLUMNS
        ),
        CheckConstraint(
            "evening_sheep_total IS NULL OR evening_sheep_total >= 0",
            name="ck_evening_sheep_nonnegative",
        ),
        CheckConstraint(
            "evening_goat_total IS NULL OR evening_goat_total >= 0",
            name="ck_evening_goat_nonnegative",
        ),
        UniqueConstraint("count_type", "count_date", name="uq_small_count_type_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    count_type: Mapped[str] = mapped_column(String(20), index=True)
    count_date: Mapped[date] = mapped_column(Date, index=True)
    sheep_male: Mapped[int] = mapped_column(Integer, default=0)
    sheep_female: Mapped[int] = mapped_column(Integer, default=0)
    goat_male: Mapped[int] = mapped_column(Integer, default=0)
    goat_female: Mapped[int] = mapped_column(Integer, default=0)
    male_lamb: Mapped[int] = mapped_column(Integer, default=0)
    female_lamb: Mapped[int] = mapped_column(Integer, default=0)
    male_kid: Mapped[int] = mapped_column(Integer, default=0)
    female_kid: Mapped[int] = mapped_column(Integer, default=0)
    hogget: Mapped[int] = mapped_column(Integer, default=0)
    yearling_goat: Mapped[int] = mapped_column(Integer, default=0)
    ram: Mapped[int] = mapped_column(Integer, default=0)
    buck: Mapped[int] = mapped_column(Integer, default=0)
    evening_sheep_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evening_goat_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    updated_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class SmallLivestockLoss(Base, TimestampMixin):
    __tablename__ = "small_livestock_losses"
    __table_args__ = (
        CheckConstraint(
            "livestock_type IN ('SHEEP','GOAT')", name="ck_small_loss_type"
        ),
        CheckConstraint("quantity > 0", name="ck_small_loss_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    loss_date: Mapped[date] = mapped_column(Date, index=True)
    livestock_type: Mapped[str] = mapped_column(String(20), index=True)
    animal_category: Mapped[str] = mapped_column(String(80), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unnatural_loss: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reason: Mapped[str] = mapped_column(Text)
    herder_id: Mapped[str | None] = mapped_column(
        ForeignKey("herders.id"), nullable=True
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    updated_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class FinanceEntry(Base, TimestampMixin):
    __tablename__ = "finance_entries"
    __table_args__ = (
        CheckConstraint("entry_type IN ('INCOME','EXPENSE')", name="ck_finance_type"),
        CheckConstraint("amount > 0", name="ck_finance_amount_positive"),
        CheckConstraint(
            "livestock_module IN ('horses','cattle','small_livestock','general')",
            name="ck_finance_module",
        ),
        CheckConstraint(
            "category IS NULL OR category IN ('Малчинд','Өвс тэжээлд','Татварт','Хашаа хороонд','Бусад ажлын хөлсөнд','Түлшинд','Бусад')",
            name="ck_finance_category",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    entry_type: Mapped[str] = mapped_column(String(20), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    livestock_module: Mapped[str] = mapped_column(String(30), index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    archive_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    updated_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class Herder(Base, TimestampMixin):
    __tablename__ = "herders"
    __table_args__ = (
        CheckConstraint(
            "module IN ('horses','cattle','small_livestock')", name="ck_herders_module"
        ),
        UniqueConstraint("registration_number", name="uq_herders_registration_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    module: Mapped[str] = mapped_column(String(30), index=True)
    last_name: Mapped[str] = mapped_column(String(120))
    first_name: Mapped[str] = mapped_column(String(120), index=True)
    registration_number: Mapped[str] = mapped_column(String(30))
    started_date: Mapped[date] = mapped_column(Date)
    ended_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    updated_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ImageAsset(Base):
    __tablename__ = "image_assets"
    __table_args__ = (
        CheckConstraint(
            "owner_type IN ('horse','cattle')", name="ck_images_owner_type"
        ),
        CheckConstraint("kind IN ('MAIN','DETAIL','LAYOUT')", name="ck_images_kind"),
        CheckConstraint(
            "size_bytes > 0 AND width > 0 AND height > 0", name="ck_images_dimensions"
        ),
        Index("ix_images_owner", "owner_type", "owner_id", "kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    owner_type: Mapped[str] = mapped_column(String(20))
    owner_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(20))
    storage_key: Mapped[str] = mapped_column(Text, unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        CheckConstraint(
            "module IN ('horses','cattle','small_livestock')",
            name="ck_snapshots_module",
        ),
        CheckConstraint("count >= 0", name="ck_snapshots_count_nonnegative"),
        UniqueConstraint("module", "snapshot_date", name="uq_snapshot_module_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    module: Mapped[str] = mapped_column(String(30), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    count: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(30), default="MANUAL")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class DashboardPreference(Base):
    __tablename__ = "dashboard_preferences"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    visible_widgets: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_idempotency_user_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(100))
    endpoint: Mapped[str] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_json: Mapped[str] = mapped_column(Text)
    status_code: Mapped[int] = mapped_column(Integer, default=200)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
