import { Unplug } from "lucide-react";
import {
  missingConnections,
  type ConnectionKey,
} from "../services/connections";

export default function ConnectionNotice({
  feature,
  compact = false,
}: {
  feature: ConnectionKey;
  compact?: boolean;
}) {
  const item = missingConnections[feature];
  return (
    <div
      className={"connection-notice " + (compact ? "compact" : "")}
      role="note"
    >
      <Unplug size={18} />
      <div>
        <strong>Collegamento da realizzare · {item.label}</strong>
        <p>{item.detail}</p>
      </div>
      <span className="pill pending">Da fare</span>
    </div>
  );
}
