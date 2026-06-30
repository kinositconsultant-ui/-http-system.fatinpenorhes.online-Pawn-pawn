import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";

import { AuthProvider } from "@/context/AuthContext";
import { LangProvider } from "@/context/LangContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import ModuleGuard from "@/components/ModuleGuard";

import PublicLayout from "@/layouts/PublicLayout";
import AdminLayout from "@/layouts/AdminLayout";

import Home from "@/pages/public/Home";
import AuctionPublic from "@/pages/public/AuctionPublic";
import Warehouse from "@/pages/public/Warehouse";
import About from "@/pages/public/About";
import Contact from "@/pages/public/Contact";
import Services from "@/pages/public/Services";
import Simulasaun from "@/pages/public/Simulasaun";
import FAQ from "@/pages/public/FAQ";

import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Clients from "@/pages/Clients";
import Items from "@/pages/Items";
import Contracts from "@/pages/Contracts";
import Payments from "@/pages/Payments";
import Auctions from "@/pages/Auctions";
import Reports from "@/pages/Reports";
import Users from "@/pages/Users";
import Settings from "@/pages/Settings";
import AuditLog from "@/pages/AuditLog";
import Finance from "@/pages/Finance";

function App() {
  return (
    <div className="App">
      <LangProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              {/* Public site */}
              <Route element={<PublicLayout />}>
                <Route path="/" element={<Home />} />
                <Route path="/about" element={<About />} />
                <Route path="/services" element={<Services />} />
                <Route path="/auction" element={<AuctionPublic />} />
                <Route path="/warehouse" element={<Warehouse />} />
                <Route path="/simulasaun" element={<Simulasaun />} />
                <Route path="/faq" element={<FAQ />} />
                <Route path="/contact" element={<Contact />} />
              </Route>

              {/* Auth */}
              <Route path="/login" element={<Login />} />

              {/* Admin */}
              <Route
                element={
                  <ProtectedRoute>
                    <AdminLayout />
                  </ProtectedRoute>
                }
              >
                <Route path="/dashboard" element={<ModuleGuard module="dashboard" label="Dashboard"><Dashboard /></ModuleGuard>} />
                <Route path="/clients" element={<ModuleGuard module="clients" label="Clients"><Clients /></ModuleGuard>} />
                <Route path="/items" element={<ModuleGuard module="items" label="Pawn Items"><Items /></ModuleGuard>} />
                <Route path="/contracts" element={<ModuleGuard module="contracts" label="Contracts"><Contracts /></ModuleGuard>} />
                <Route path="/payments" element={<ModuleGuard module="payments" label="Payments"><Payments /></ModuleGuard>} />
                <Route path="/auctions" element={<ModuleGuard module="auctions" label="Auctions"><Auctions /></ModuleGuard>} />
                <Route path="/reports" element={<ModuleGuard module="reports" label="Reports"><Reports /></ModuleGuard>} />
                <Route path="/finance" element={<ModuleGuard module="finance" label="Finance"><Finance /></ModuleGuard>} />
                <Route path="/users" element={<ModuleGuard module="users" label="Users"><Users /></ModuleGuard>} />
                <Route path="/settings" element={<ModuleGuard module="settings" label="Settings"><Settings /></ModuleGuard>} />
                <Route path="/audit-log" element={<ModuleGuard module="audit_log" label="Audit Log"><AuditLog /></ModuleGuard>} />
              </Route>

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
          <Toaster position="top-right" richColors />
        </AuthProvider>
      </LangProvider>
    </div>
  );
}

export default App;
