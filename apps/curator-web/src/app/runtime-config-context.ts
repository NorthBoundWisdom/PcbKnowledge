import { createContext } from "react";

import type { RuntimeConfig } from "../config/runtime-config";

export const RuntimeConfigContext = createContext<RuntimeConfig | null>(null);
