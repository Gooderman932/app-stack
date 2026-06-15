export type MealType = "breakfast" | "lunch" | "dinner" | "snack";

export interface MealPlanMonth {
  id: string;
  month_number: number;
  title: string;
  theme: string | null;
  target_kcal: number;
  description: string | null;
}

export interface MealSlot {
  id: string;
  plan_month_id: string;
  day_number: number;
  meal_type: MealType;
  name: string;
  target_kcal: number | null;
  prep_time_minutes: number | null;
  instructions: string | null;
}

export interface MealIngredient {
  id: string;
  meal_slot_id: string;
  quantity: number;
  unit: string;
  notes: string | null;
  ingredients: { name: string; category: string } | null;
}

export interface RecipeCard {
  id: string;
  meal_slot_id: string;
  content: string;
}

export interface ShopVariant {
  id: string;
  variant_name: string;
  price_cents: number;
  stock_qty: number;
}

export interface ShopProduct {
  id: string;
  sku: string;
  name: string;
  description: string | null;
  ingredients_list: string | null;
  allergen_info: string[];
  base_price_cents: number;
  weight_grams: number | null;
  shop_product_variants: ShopVariant[];
}

export interface ProducerListing {
  id: string;
  producer_id: string;
  ingredient_id: string;
  quantity_available: number;
  unit: string;
  price_per_unit_cents: number;
  availability_start: string | null;
  availability_end: string | null;
  status: "active" | "paused" | "sold_out" | "expired";
  ingredients?: { name: string; category: string } | null;
}
