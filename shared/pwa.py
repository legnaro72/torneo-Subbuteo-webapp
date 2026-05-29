import streamlit.components.v1 as components


def inject_pwa_assets():
    """Register PWA manifest and service worker from Streamlit pages."""
    components.html(
        """
        <script>
        const parentDoc = window.parent.document;
        const manifestData = {
          name: "Super Suite Subbuteo",
          short_name: "Superba",
          description: "Suite mobile per tornei Subbuteo Superba",
          start_url: "/",
          scope: "/",
          display: "standalone",
          background_color: "#f8fafc",
          theme_color: "#1d3557"
        };
        window.parent.addEventListener("beforeinstallprompt", function(event) {
          window.parent.__subbuteoBeforeInstallPrompt = true;
          window.parent.__subbuteoInstallPromptEvent = event;
        });
        if (!parentDoc.querySelector('link[rel="manifest"]')) {
          const manifest = parentDoc.createElement("link");
          manifest.rel = "manifest";
          manifest.href = URL.createObjectURL(
            new Blob([JSON.stringify(manifestData)], {type: "application/manifest+json"})
          );
          parentDoc.head.appendChild(manifest);
        }
        let theme = parentDoc.querySelector('meta[name="theme-color"]');
        if (!theme) {
          theme = parentDoc.createElement("meta");
          theme.name = "theme-color";
          parentDoc.head.appendChild(theme);
        }
        theme.content = "#1d3557";
        </script>
        """,
        height=0,
        width=0,
    )


def show_pwa_diagnostics():
    """Small browser-side diagnostics panel for PWA installability checks."""
    components.html(
        """
        <div id="pwa-diagnostics" style="font-family: system-ui, sans-serif; font-size: 13px; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: white; color: #111;">
          Verifica PWA in corso...
        </div>
        <script>
        (async function() {
          const out = document.getElementById("pwa-diagnostics");
          const parentDoc = window.parent.document;
          const manifestLink = parentDoc.querySelector('link[rel="manifest"]');
          const lines = [];
          lines.push("URL pagina: " + window.parent.location.href);
          lines.push("Manifest link: " + (manifestLink ? manifestLink.href : "NON TROVATO"));
          if (manifestLink) {
            try {
              const response = await fetch(manifestLink.href, { cache: "no-store" });
              lines.push("Manifest HTTP: " + response.status + " " + (response.headers.get("content-type") || "content-type assente"));
              const manifest = await response.json();
              lines.push("name: " + manifest.name);
              lines.push("short_name: " + manifest.short_name);
              lines.push("start_url: " + manifest.start_url);
              lines.push("icons: " + (manifest.icons ? manifest.icons.length : 0));
              lines.push("shortcuts: " + (manifest.shortcuts ? manifest.shortcuts.length : 0));
            } catch (e) {
              lines.push("Manifest errore: " + e.message);
            }
          }
          lines.push("ServiceWorker support: " + ("serviceWorker" in window.parent.navigator));
          if ("serviceWorker" in window.parent.navigator) {
            try {
              const regs = await window.parent.navigator.serviceWorker.getRegistrations();
              lines.push("ServiceWorker registrati: " + regs.length);
              regs.forEach((reg, idx) => lines.push("SW " + (idx + 1) + " scope: " + reg.scope));
            } catch (e) {
              lines.push("ServiceWorker errore: " + e.message);
            }
          }
          lines.push("beforeinstallprompt seen: " + (!!window.parent.__subbuteoBeforeInstallPrompt));
          out.innerHTML = "<b>Diagnostica PWA</b><br><pre style='white-space:pre-wrap;margin:6px 0 0 0'>" + lines.join("\\n") + "</pre>";
        })();
        </script>
        """,
        height=220,
        width=700,
    )
