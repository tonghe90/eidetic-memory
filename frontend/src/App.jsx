import React, { useEffect, useState } from "react";
import { Routes, Route, NavLink, useNavigate, useLocation } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Search from "./pages/Search";
import Sources from "./pages/Sources";
import Settings from "./pages/Settings";
import Onboarding from "./pages/Onboarding";

const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/search", label: "搜索" },
  { to: "/sources", label: "数据源" },
  { to: "/settings", label: "设置" },
];

function AppShell() {
  return (
    <div className="flex h-screen">
      <aside className="w-44 bg-gray-900 border-r border-gray-800 flex flex-col py-6 px-4 shrink-0">
        <h1 className="text-lg font-bold text-white mb-8 tracking-tight">LLM Wiki</h1>
        <nav className="flex flex-col gap-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? "bg-indigo-600 text-white"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto p-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/search" element={<Search />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  const [checked, setChecked] = useState(false);
  const [needsSetup, setNeedsSetup] = useState(false);
  const location = useLocation();

  useEffect(() => {
    // Skip check if already on onboarding
    if (location.pathname === "/setup") {
      setChecked(true);
      return;
    }
    fetch("/connectors/setup-status")
      .then((r) => r.json())
      .then((statuses) => {
        // Needs setup if no connector is authenticated at all
        const anyAuthed = Object.values(statuses).some(Boolean);
        setNeedsSetup(!anyAuthed);
        setChecked(true);
      })
      .catch(() => setChecked(true));
  }, []);

  if (!checked) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-gray-500 text-sm">加载中...</div>
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/setup" element={<Onboarding />} />
      <Route
        path="/*"
        element={needsSetup ? <Onboarding /> : <AppShell />}
      />
    </Routes>
  );
}
