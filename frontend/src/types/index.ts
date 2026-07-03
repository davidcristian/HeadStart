/** Types mirroring the backend Pydantic schemas (see backend/app/schemas). */

export type { Json } from "./json";
export type {
  Source,
  SourceCreate,
  SourceDetectResult,
  JobPostingPreview,
  SourceTestResult,
} from "./source";
export type { DeliveryFailure, Search, SearchCreate, SearchRunResult, FeedUrl } from "./search";
export type { NotificationTarget, TargetCreate } from "./target";
export type {
  JobStatus,
  Job,
  JobApplyResult,
  JobCoverLetterResult,
  JobResumeResult,
  ApplicationLog,
} from "./job";
export type {
  ApplicationPipelineStage,
  ApplicationAttemptSummary,
  ApplicationPipelineItem,
} from "./application";
export type {
  PlanId,
  PlanLimits,
  PlanUsage,
  PlanFeatures,
  AccountPlan,
  AdsConfig,
  Meta,
  Health,
} from "./meta";
export type {
  BillingPeriod,
  BillingStatus,
  PromoType,
  PromoValidation,
  PromoCode,
  PromoRedemption,
} from "./billing";
export type { User, AdminUser, AccessTokenResponse } from "./auth";
export type { AdminSearchError, AdminStats, DataRequestLog } from "./admin";
export type { SiteCredential, CredentialCreate, CredentialExport } from "./credentials";
export type {
  ProfileLinks,
  WorkExperienceEntry,
  EducationEntry,
  LanguageEntry,
  ProfileData,
  ResumeFileMeta,
  Profile,
  UserDataExport,
} from "./profile";
export type {
  Portal,
  PortalCategory,
  PortalList,
  PortalSearchRequest,
  PortalSearchResult,
  PortalSubscribeRequest,
  PortalSubscribeResult,
} from "./portal";
export type {
  AiPurposeId,
  AiPurposeOption,
  PurposePreference,
  PurposePreferencePatch,
  SummaryProviderId,
  SummaryProviderOption,
  SummaryPreferences,
  SummaryPreferencesUpdate,
} from "./summaryPreferences";
