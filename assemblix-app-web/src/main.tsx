import { createRoot } from "react-dom/client";
import { Providers } from "@/app/providers";
import { captureUtmParams, saveUtmToStorage } from "@/shared/lib/utm";
import "./app/index.css";

saveUtmToStorage(captureUtmParams());

createRoot(document.getElementById("root")!).render(<Providers />);
