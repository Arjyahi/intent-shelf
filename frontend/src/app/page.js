import DiscoveryExperience from "@/components/feed/DiscoveryExperience";
import { AppStateProvider } from "@/state/AppStateContext";

export default function HomePage() {
  return (
    <AppStateProvider>
      <DiscoveryExperience />
    </AppStateProvider>
  );
}
