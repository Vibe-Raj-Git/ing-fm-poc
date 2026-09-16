import re

# 1. Update main.py to add the reset baseline endpoint before if __name__ == "__main__":
with open("main.py", "r", encoding="utf-8") as f:
    main_content = f.read()

reset_endpoint_code = """
@app.post("/api/system/reset-baseline")
def reset_baseline(payload: dict = None):
    \"\"\"
    Restores active baseline records for specified client IDs in ACTIVE_UI_CLIENT_IDS 
    while preserving historical telemetry and user-ingested rows.
    \"\"\"
    try:
        client_ids = payload.get("client_ids", ["CLI101"]) if payload else ["CLI101"]
        for cid in client_ids:
            if cid in _MANDATE_SYNTH_CACHE:
                del _MANDATE_SYNTH_CACHE[cid]
        return {
            "status": "success",
            "message": f"Successfully reset baseline for client IDs: {client_ids}",
            "restored_clients": client_ids
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
"""

if "def reset_baseline" not in main_content:
    main_content = main_content.replace('if __name__ == "__main__":', reset_endpoint_code)
    with open("main.py", "w", encoding="utf-8") as f:
        f.write(main_content)
    print("Successfully updated main.py with /api/system/reset-baseline endpoint.")
else:
    print("main.py already contains reset_baseline endpoint.")


# 2. Update frontend/src/App.jsx to add the ShieldCheck button beside RefreshCw
with open("frontend/src/App.jsx", "r", encoding="utf-8") as f:
    app_content = f.read()

old_button_block = """              <button 
                onClick={fetchDashboardData} 
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition"
                title="Refresh database records"
                disabled={isLoading}
              >
                <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
              </button>"""

new_button_block = """              <button 
                onClick={fetchDashboardData} 
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition"
                title="Refresh database records"
                disabled={isLoading}
              >
                <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
              </button>
              <button 
                onClick={async () => {
                  setIsLoading(true);
                  try {
                    await fetch('/api/system/reset-baseline', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ client_ids: ACTIVE_UI_CLIENT_IDS })
                    });
                    setDeckOverrides({});
                    await fetchDashboardData();
                  } catch (err) {
                    console.error("Reset failed:", err);
                  } finally {
                    setIsLoading(false);
                  }
                }}
                className="p-1.5 rounded-lg text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 transition"
                title="Reset active clients to pristine baseline (preserves historical uploads)"
                disabled={isLoading}
              >
                <ShieldCheck size={16} className={isLoading ? "animate-pulse" : ""} />
              </button>"""

if "ShieldCheck size={16}" not in app_content and old_button_block in app_content:
    app_content = app_content.replace(old_button_block, new_button_block)
    with open("frontend/src/App.jsx", "w", encoding="utf-8") as f:
        f.write(app_content)
    print("Successfully updated frontend/src/App.jsx with Enel Master Reset button.")
else:
    print("App.jsx already contains the reset button or target block mismatch.")