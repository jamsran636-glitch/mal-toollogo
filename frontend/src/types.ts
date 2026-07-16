export type Role = "OWNER" | "HORSE_KEEPER" | "CATTLE_KEEPER" | "SHEEP_KEEPER";
export type ModuleKey = "horses" | "cattle" | "small_livestock" | "analytics";

export interface User {
  id: string;
  username: string;
  role: Role;
  allowed_modules: string[];
  must_change_code: boolean;
}

export interface TokenResponse {
  access_token: string;
  expires_in_seconds: number;
  user: User;
}

export interface ImageAsset {
  id: string;
  kind: string;
  original_filename: string;
  url: string;
  width: number;
  height: number;
}

export interface HorseGroup {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  version: number;
}

export interface Horse {
  id: string;
  group_id: string;
  group_name: string;
  color: string;
  birth_year: number;
  age_years: number;
  age_category: string;
  display_label: string;
  sex: "MALE" | "FEMALE";
  male_status: "STALLION" | "GELDING" | "COLT" | null;
  current_status: "ACTIVE" | "PREGNANT" | "ARCHIVED" | "DECEASED";
  mother_id: string | null;
  mother_label: string | null;
  father_id: string | null;
  father_label: string | null;
  additional_info: string | null;
  archived_at: string | null;
  archive_note: string | null;
  unnatural_loss: boolean;
  version: number;
  images: ImageAsset[];
  main_image: ImageAsset | null;
  layout_image: ImageAsset | null;
  indent: number;
  relation_note: string | null;
}

export interface Cattle {
  id: string;
  ear_tag: string;
  color: string;
  birth_year: number;
  age_years: number;
  age_category: string;
  sex: "MALE" | "FEMALE";
  is_bull: boolean;
  current_status: "ACTIVE" | "ARCHIVED" | "DECEASED";
  mother_id: string | null;
  mother_label: string | null;
  additional_info: string | null;
  archived_at: string | null;
  archive_note: string | null;
  unnatural_loss: boolean;
  version: number;
  images: ImageAsset[];
  main_image: ImageAsset | null;
  layout_image: ImageAsset | null;
}

export interface Stats {
  total: number;
  eligible_males: number;
  eligible_females: number;
  offspring: number;
  breeding_males: number;
}

export interface Census {
  id: string;
  count_type: "FULL" | "EVENING";
  count_date: string;
  version: number;
  total: number;
  sheep_total: number;
  goat_total: number;
  adult_total: number;
  note: string | null;
  [key: string]: string | number | null;
}

export interface FinanceEntry {
  id: string;
  entry_type: "INCOME" | "EXPENSE";
  amount: number;
  entry_date: string;
  livestock_module: string;
  category: string | null;
  description: string;
  is_archived: boolean;
  version: number;
}

export interface Herder {
  id: string;
  module: string;
  last_name: string;
  first_name: string;
  registration_number: string;
  started_date: string;
  ended_date: string | null;
  note: string | null;
  is_active: boolean;
  version: number;
}

export interface AuditRow {
  id: number;
  username: string;
  role: string;
  action: string;
  module: string | null;
  entity_type: string | null;
  entity_id: string | null;
  previous_data: unknown;
  new_data: unknown;
  detail: string | null;
  success: boolean;
  created_at: string;
}

export interface Dashboard {
  livestock_counts: Record<string, number>;
  profit_by_livestock: Record<string, { income: number; expense: number; profit: number }>;
  mortality: Record<string, { total: number; abnormal: number }>;
  growth: Array<{ year: number; horses: number | null; cattle: number | null; small_livestock: number | null }>;
  expense_categories: Record<string, number>;
  adult_males: Record<string, { total: number; age_structure?: Record<string, number>; structure?: Record<string, number> }>;
  monthly_balance: Array<{ month: number; income: number; expense: number; profit: number }>;
}
