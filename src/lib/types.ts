export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

/** ---- Enums ---- */
export type UserRole = 'consumer' | 'producer' | 'admin';
export type PipelineType = 'national_bulk' | 'regional_fresh' | 'producer_direct' | 'customer_self_source' | 'not_eligible';
export type TcsStatus = 'tcs' | 'non_tcs' | 'shelf_stable';
export type OrderStatus = 'pending' | 'paid' | 'fulfilling' | 'shipped' | 'delivered' | 'cancelled' | 'refunded';
export type SubscriptionTier = 'free' | 'premium';

/** ---- Core row shapes (mirrors Supabase schema) ---- */
export interface Profile {
  id: string;
  email: string;
  role: UserRole;
  display_name: string | null;
  zip_code: string | null;
  subscription_tier: SubscriptionTier;
  revenuecat_customer_id: string | null;
  created_at: string;
}

export interface MealPlan {
  id: string;
  month_number: number;
  title: string;
  theme: string | null;
  kcal_target: number | null;
  description: string | null;
}

export interface MealSlot {
  id: string;
  meal_plan_id: string;
  slot_label: string;
  meal_type: 'breakfast' | 'lunch' | 'dinner' | 'snack';
  servings: number;
  estimated_cost_usd: number | null;
}

export interface MealIngredient {
  id: string;
  meal_slot_id: string;
  ingredient_name: string;
  quantity: string;
  unit: string | null;
  notes: string | null;
}

export interface RecipeCard {
  id: string;
  meal_slot_id: string;
  title: string;
  prep_minutes: number | null;
  cook_minutes: number | null;
  instructions: string[];
  tips: string | null;
}

export interface IngredientClassification {
  id: string;
  ingredient_name: string;
  tcs_status: TcsStatus;
  is_shelf_stable: boolean;
  requires_license: boolean;
  allowed_pipelines: PipelineType[];
  mf3138_category: string | null;
  notes: string | null;
}

export interface Product {
  id: string;
  name: string;
  description: string | null;
  price_usd: number;
  category: string | null;
  image_url: string | null;
  is_active: boolean;
}

export interface ProductVariant {
  id: string;
  product_id: string;
  sku: string;
  size_label: string;
  price_usd: number;
  inventory_count: number;
}

export interface CartItem {
  variantId: string;
  productId: string;
  name: string;
  sizeLabel: string;
  price: number;
  quantity: number;
}

export interface ProducerProfile {
  id: string;
  user_id: string;
  farm_name: string;
  contact_email: string | null;
  city: string | null;
  zip_code: string | null;
  certifications: string[];
  bio: string | null;
  is_approved: boolean;
}

export interface ProducerListing {
  id: string;
  producer_id: string;
  ingredient_name: string;
  pipeline: PipelineType;
  quantity_available_lbs: number | null;
  price_per_lb_usd: number | null;
  is_active: boolean;
  description: string | null;
}

/** ---- Phase 2 Fresh Box ---- */
export interface FreshBoxSubscription {
  id: string;
  user_id: string;
  zip_code: string;
  plan_size: 'small' | 'medium' | 'large';
  frequency: 'weekly' | 'biweekly';
  price_usd: number;
  status: 'active' | 'paused' | 'cancelled';
  next_delivery_date: string | null;
  created_at: string;
}

export interface Database {
  public: {
    Tables: {
      profiles: { Row: Profile; Insert: Partial<Profile>; Update: Partial<Profile> };
      meal_plans: { Row: MealPlan; Insert: Partial<MealPlan>; Update: Partial<MealPlan> };
      meal_slots: { Row: MealSlot; Insert: Partial<MealSlot>; Update: Partial<MealSlot> };
      meal_ingredients: { Row: MealIngredient; Insert: Partial<MealIngredient>; Update: Partial<MealIngredient> };
      recipe_cards: { Row: RecipeCard; Insert: Partial<RecipeCard>; Update: Partial<RecipeCard> };
      ingredient_classifications: { Row: IngredientClassification; Insert: Partial<IngredientClassification>; Update: Partial<IngredientClassification> };
      products: { Row: Product; Insert: Partial<Product>; Update: Partial<Product> };
      product_variants: { Row: ProductVariant; Insert: Partial<ProductVariant>; Update: Partial<ProductVariant> };
      producer_profiles: { Row: ProducerProfile; Insert: Partial<ProducerProfile>; Update: Partial<ProducerProfile> };
      producer_listings: { Row: ProducerListing; Insert: Partial<ProducerListing>; Update: Partial<ProducerListing> };
      fresh_box_subscriptions: { Row: FreshBoxSubscription; Insert: Partial<FreshBoxSubscription>; Update: Partial<FreshBoxSubscription> };
    };
  };
}
