import type { Json } from "./json";

export interface NotificationTarget {
  id: number;
  name: string;
  type: string;
  config: Json;
  created_at: string;
}

export type TargetCreate = Omit<NotificationTarget, "id" | "created_at">;
