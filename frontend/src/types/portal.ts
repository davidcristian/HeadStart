/** Curated employer portal from GET /portals. */

export type PortalCategory = "big_tech" | "unicorn" | "ai";

export type Portal = {
  id: string;
  company_name: string;
  category: PortalCategory;
  adapter_key: string;
  base_url: string;
  default_config: Record<string, unknown>;
  supports_auto_apply: boolean;
  allowed_on_plan: boolean;
  already_added: boolean;
};

export type PortalList = {
  items: Portal[];
  categories: PortalCategory[];
};
