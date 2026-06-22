import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";

import { AuthProvider } from "@/context/AuthContext";
import { LangProvider } from "@/context/LangContext";
import ProtectedRoute from "@/components/ProtectedRoute";

import PublicLayout from "@/layouts/PublicLayout";
import AdminLayout from "@/layouts/AdminLayout";

import Home from "@/pages/public/Home";
import AuctionPublic from "@/pages/public/AuctionPublic";
import Warehouse from "@/pages/public/Warehouse";
import About from "@/pages/public/About";
import Contact from "@/pages/public/Contact";

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
                <Route path="/auction" element={<AuctionPublic />} />
                <Route path="/warehouse" element={<Warehouse />} />
                <Route path="/about" element={<About />} />
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
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/clients" element={<Clients />} />
                <Route path="/items" element={<Items />} />
                <Route path="/contracts" element={<Contracts />} />
                <Route path="/payments" element={<Payments />} />
                <Route path="/auctions" element={<Auctions />} />
                <Route path="/reports" element={<Reports />} />
                <Route path="/finance" element={<Finance />} />
                <Route path="/users" element={<Users />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/audit-log" element={<AuditLog />} />
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
