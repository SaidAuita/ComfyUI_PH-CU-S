import { app } from "../../scripts/app.js";

function connectBridge() {
    const url = new URL(`/phcus/ws?platform=cm`, window.location.href);
    url.protocol = url.protocol.replace("http", "ws");

    const ws = new WebSocket(url.href);

    ws.onopen = () => console.log("[PH-CU-S] bridge connected");

    ws.onmessage = async (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.loadWorkflow) {
                console.log("[PH-CU-S] loading workflow into graph");
                await app.loadGraphData(msg.loadWorkflow);
            }
            if (msg.loadAndQueue) {
                console.log("[PH-CU-S] loading workflow and queuing");
                await app.loadGraphData(msg.loadAndQueue);
                app.queuePrompt(0, 1);
            }
            if (msg.queue) {
                console.log("[PH-CU-S] queue prompt triggered");
                app.queuePrompt(0, 1);
            }
        } catch (e) {
            console.error("[PH-CU-S] message parse error", e);
        }
    };

    ws.onclose = () => {
        console.log("[PH-CU-S] bridge disconnected, retry in 2s");
        setTimeout(connectBridge, 2000);
    };

    ws.onerror = (e) => console.error("[PH-CU-S] bridge error", e);
}

app.registerExtension({
    name: "PHCUS.Bridge",
    async setup() {
        console.log("[PH-CU-S] extension loaded");
        connectBridge();
    }
});
