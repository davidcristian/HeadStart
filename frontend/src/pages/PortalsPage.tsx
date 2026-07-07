/** Search curated FAANG-adjacent and unicorn employer portals in one place (Pro+). */

import { Banner } from "../components/ui";
import { PortalsResultsCard } from "./portals/PortalsResultsCard";
import { PortalsSearchCard } from "./portals/PortalsSearchCard";
import { PortalsSubscribeCard } from "./portals/PortalsSubscribeCard";
import { PortalsUpgradePrompt } from "./portals/PortalsUpgradePrompt";
import { usePortalsPage } from "./portals/usePortalsPage";

export function PortalsPage() {
  const page = usePortalsPage();

  if (!page.portalSearchAllowed) {
    return <PortalsUpgradePrompt plan={page.plan} />;
  }

  return (
    <div className="page-stack">
      <h1>Company search</h1>
      <p className="muted portal-page-intro">
        Search open roles across curated employer career sites, then subscribe to alerts without
        hand-configuring each board.
      </p>

      {page.error && <Banner kind="error">{page.error}</Banner>}
      {page.notice && <Banner kind="success">{page.notice}</Banner>}

      <PortalsSearchCard
        category={page.category}
        setCategory={page.setCategory}
        categories={page.categories}
        keywords={page.keywords}
        setKeywords={page.setKeywords}
        location={page.location}
        setLocation={page.setLocation}
        workplace={page.workplace}
        setWorkplace={page.setWorkplace}
        catalogItems={page.catalogItems}
        selectedIds={page.selectedIds}
        selectPortals={page.selectPortals}
        togglePortal={page.togglePortal}
        portalsPending={page.portals.isPending}
        portalsError={page.portals.isError}
        onSearch={page.runSearch}
        searchPending={page.searchPortals.isPending}
      />

      {page.results && <PortalsResultsCard results={page.results} />}

      <PortalsSubscribeCard
        targets={page.targets}
        targetId={page.targetId}
        setTargetId={page.setTargetId}
        interval={page.interval}
        setInterval={page.setInterval}
        onCreateAlerts={page.createAlerts}
        subscribePending={page.subscribePortals.isPending}
      />
    </div>
  );
}
