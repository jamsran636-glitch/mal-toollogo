from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Role = Literal["OWNER", "HORSE_KEEPER", "CATTLE_KEEPER", "SHEEP_KEEPER"]
Sex = Literal["MALE", "FEMALE"]
Module = Literal["horses", "cattle", "small_livestock", "general"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=8, max_length=128)


class UserInfo(BaseModel):
    id: str
    username: str
    role: Role
    allowed_modules: list[str]
    must_change_code: bool


class TokenResponse(BaseModel):
    access_token: str
    expires_in_seconds: int
    token_type: str = "bearer"
    user: UserInfo


class ChangeCodeRequest(BaseModel):
    current_code: str = Field(min_length=8, max_length=128)
    new_code: str = Field(min_length=10, max_length=128)


class AdminRotateCodeRequest(BaseModel):
    new_code: str = Field(min_length=10, max_length=128)
    must_change_code: bool = True


class AuditRead(BaseModel):
    id: int
    actor_user_id: str | None
    username: str
    role: str
    action: str
    module: str | None
    entity_type: str | None
    entity_id: str | None
    previous_data: Any
    new_data: Any
    detail: str | None
    request_id: str | None
    ip_address: str | None
    success: bool
    created_at: datetime


class VersionedUpdate(BaseModel):
    expected_version: int = Field(ge=1)


class HorseGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)


class HorseGroupUpdate(VersionedUpdate):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None


class HorseGroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str | None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class HorseBase(BaseModel):
    color: str = Field(min_length=1, max_length=160)
    birth_year: int = Field(ge=1980, le=2100)
    sex: Sex
    male_status: Literal["STALLION", "GELDING", "COLT"] | None = None
    current_status: Literal["ACTIVE", "PREGNANT"] = "ACTIVE"
    mother_id: str | None = None
    father_id: str | None = None
    additional_info: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def validate_gender_status(self):
        if self.sex == "FEMALE" and self.male_status is not None:
            raise ValueError("Эм адуунд эр адууны ангилал сонгохгүй")
        if self.sex == "MALE" and self.current_status == "PREGNANT":
            raise ValueError("Зөвхөн эм адуу хээлтэй төлөвтэй байна")
        return self


class HorseCreate(HorseBase):
    group_id: str


class HorseUpdate(VersionedUpdate):
    color: str | None = Field(default=None, min_length=1, max_length=160)
    birth_year: int | None = Field(default=None, ge=1980, le=2100)
    sex: Sex | None = None
    male_status: Literal["STALLION", "GELDING", "COLT"] | None = None
    current_status: Literal["ACTIVE", "PREGNANT"] | None = None
    mother_id: str | None = None
    father_id: str | None = None
    additional_info: str | None = Field(default=None, max_length=10000)


class ArchiveRequest(BaseModel):
    archive_note: str = Field(min_length=1, max_length=4000)
    unnatural_loss: bool = False
    deceased: bool = False


class RestoreRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=4000)


class PermanentDeleteRequest(BaseModel):
    confirmation: Literal["УСТГАХ"]


class HorseTransferRequest(BaseModel):
    to_group_id: str
    reason: str = Field(min_length=1, max_length=4000)
    expected_version: int = Field(ge=1)


class ImageRead(BaseModel):
    id: str
    kind: str
    original_filename: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    created_at: datetime
    url: str


class HorseRead(BaseModel):
    id: str
    group_id: str
    group_name: str
    color: str
    birth_year: int
    age_years: int
    age_category: str
    display_label: str
    sex: str
    male_status: str | None
    current_status: str
    mother_id: str | None
    mother_label: str | None
    father_id: str | None
    father_label: str | None
    additional_info: str | None
    archived_at: datetime | None
    archive_note: str | None
    unnatural_loss: bool
    version: int
    images: list[ImageRead] = []
    main_image: ImageRead | None = None
    layout_image: ImageRead | None = None
    created_at: datetime
    updated_at: datetime
    indent: int = 0
    relation_note: str | None = None


class HorseTransferRead(BaseModel):
    id: int
    horse_id: str
    from_group_id: str | None
    from_group_name: str | None
    to_group_id: str
    to_group_name: str
    reason: str
    changed_by: str
    changed_by_name: str
    changed_at: datetime


class HorseStatistics(BaseModel):
    total: int
    eligible_males: int
    eligible_females: int
    offspring: int
    breeding_males: int


class CattleBase(BaseModel):
    ear_tag: str = Field(min_length=1, max_length=80)
    color: str = Field(min_length=1, max_length=160)
    birth_year: int = Field(ge=1980, le=2100)
    sex: Sex
    is_bull: bool = False
    mother_id: str | None = None
    additional_info: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def validate_bull(self):
        if self.is_bull and self.sex != "MALE":
            raise ValueError("Бух заавал эр хүйстэй байна")
        return self


class CattleCreate(CattleBase):
    pass


class CattleUpdate(VersionedUpdate):
    ear_tag: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = Field(default=None, min_length=1, max_length=160)
    birth_year: int | None = Field(default=None, ge=1980, le=2100)
    sex: Sex | None = None
    is_bull: bool | None = None
    mother_id: str | None = None
    additional_info: str | None = Field(default=None, max_length=10000)


class CattleRead(BaseModel):
    id: str
    ear_tag: str
    color: str
    birth_year: int
    age_years: int
    age_category: str
    sex: str
    is_bull: bool
    current_status: str
    mother_id: str | None
    mother_label: str | None
    additional_info: str | None
    archived_at: datetime | None
    archive_note: str | None
    unnatural_loss: bool
    version: int
    images: list[ImageRead] = []
    main_image: ImageRead | None = None
    layout_image: ImageRead | None = None
    created_at: datetime
    updated_at: datetime


class CountFields(BaseModel):
    sheep_male: int = Field(default=0, ge=0)
    sheep_female: int = Field(default=0, ge=0)
    goat_male: int = Field(default=0, ge=0)
    goat_female: int = Field(default=0, ge=0)
    male_lamb: int = Field(default=0, ge=0)
    female_lamb: int = Field(default=0, ge=0)
    male_kid: int = Field(default=0, ge=0)
    female_kid: int = Field(default=0, ge=0)
    hogget: int = Field(default=0, ge=0)
    yearling_goat: int = Field(default=0, ge=0)
    ram: int = Field(default=0, ge=0)
    buck: int = Field(default=0, ge=0)
    evening_sheep_total: int | None = Field(default=None, ge=0)
    evening_goat_total: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=4000)


class SmallCountCreate(CountFields):
    count_type: Literal["FULL", "EVENING"]
    count_date: date

    @model_validator(mode="after")
    def validate_type_fields(self):
        if self.count_type == "EVENING" and (
            self.evening_sheep_total is None or self.evening_goat_total is None
        ):
            raise ValueError("Оройн тоонд хонь, ямааны нийт тоо шаардлагатай")
        if self.count_type == "FULL" and (
            self.evening_sheep_total is not None or self.evening_goat_total is not None
        ):
            raise ValueError("Бүрэн тооллогод оройн нийт талбар ашиглахгүй")
        return self


class SmallCountUpdate(SmallCountCreate):
    expected_version: int = Field(ge=1)
    correction_reason: str = Field(min_length=1, max_length=4000)


class SmallLossCreate(BaseModel):
    loss_date: date
    livestock_type: Literal["SHEEP", "GOAT"]
    animal_category: str = Field(min_length=1, max_length=80)
    quantity: int = Field(gt=0)
    unnatural_loss: bool = False
    reason: str = Field(min_length=1, max_length=4000)
    herder_id: str | None = None


class SmallLossUpdate(SmallLossCreate):
    expected_version: int = Field(ge=1)


EXPENSE_CATEGORIES = (
    "Малчинд",
    "Өвс тэжээлд",
    "Татварт",
    "Хашаа хороонд",
    "Бусад ажлын хөлсөнд",
    "Түлшинд",
    "Бусад",
)


class FinanceCreate(BaseModel):
    entry_type: Literal["INCOME", "EXPENSE"]
    amount: int = Field(gt=0)
    entry_date: date = Field(default_factory=date.today)
    livestock_module: Module
    category: str | None = None
    description: str = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def validate_category(self):
        if self.entry_type == "EXPENSE" and self.category not in EXPENSE_CATEGORIES:
            raise ValueError("Зарлагын ангилал буруу")
        if self.entry_type == "INCOME" and self.category is not None:
            raise ValueError("Орлогод зарлагын ангилал ашиглахгүй")
        return self


class FinanceUpdate(FinanceCreate):
    expected_version: int = Field(ge=1)


class HerderCreate(BaseModel):
    module: Literal["horses", "cattle", "small_livestock"]
    last_name: str = Field(min_length=1, max_length=120)
    first_name: str = Field(min_length=1, max_length=120)
    registration_number: str = Field(min_length=5, max_length=30)
    started_date: date
    ended_date: date | None = None
    note: str | None = Field(default=None, max_length=4000)


class HerderUpdate(HerderCreate):
    expected_version: int = Field(ge=1)


class SnapshotCreate(BaseModel):
    module: Literal["horses", "cattle", "small_livestock"]
    snapshot_date: date
    count: int = Field(ge=0)
    note: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def january_first(self):
        if (self.snapshot_date.month, self.snapshot_date.day) != (1, 1):
            raise ValueError("Түүхэн үлдэгдлийн огноо 1-р сарын 1 байна")
        return self


class DashboardPreferenceUpdate(BaseModel):
    visible_widgets: list[
        Literal[
            "profit",
            "counts",
            "mortality",
            "growth",
            "expenses",
            "adult_males",
            "balance",
        ]
    ]


class BackupRestoreConfirmation(BaseModel):
    confirmation: Literal["RESTORE"]
