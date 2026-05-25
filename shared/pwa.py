import streamlit.components.v1 as components


def inject_pwa_assets():
    """Register PWA manifest and service worker from Streamlit pages."""
    components.html(
        """
        <script>
        const parentDoc = window.parent.document;
        if (!parentDoc.querySelector('link[rel="manifest"]')) {
          const manifest = parentDoc.createElement("link");
          manifest.rel = "manifest";
          manifest.href = "/app/static/manifest.webmanifest";
          parentDoc.head.appendChild(manifest);
        }
        let theme = parentDoc.querySelector('meta[name="theme-color"]');
        if (!theme) {
          theme = parentDoc.createElement("meta");
          theme.name = "theme-color";
          parentDoc.head.appendChild(theme);
        }
        theme.content = "#1d3557";
        if ("serviceWorker" in window.parent.navigator) {
          fetch("/app/static/service-worker.js", { cache: "no-store" })
            .then(function(response) {
              const type = response.headers.get("content-type") || "";
              if (response.ok && type.indexOf("javascript") !== -1) {
                return window.parent.navigator.serviceWorker.register("/app/static/service-worker.js");
              }
            })
            .catch(function() {});
        }
        </script>
        """,
        height=0,
        width=0,
    )
