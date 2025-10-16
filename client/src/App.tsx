import { BrowserRouter, Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { useState } from "react";

import { authStorage } from "./utils/auth";
import LoginForm from "./components/LoginForm";
import RegisterForm from "./components/RegisterForm";
import GamePage from "./components/VoxelGrid"; // היה VoxelGrid.tsx – הייצוא הדיפולטי נקרא כאן GamePage
import TopBar from "./components/TopBar";

// שמירה על מסלול /game למשתמשים מחוברים בלבד
// function PrivateRoute({ children }: { children: JSX.Element }) {
//   const isAuthed = authStorage.isAuthenticated();
//   return isAuthed ? children : <Navigate to="/auth" replace />;
// }

// דף התחברות/הרשמה עם טאבים
function AuthPage() {
  const navigate = useNavigate()
  if (authStorage.isAuthenticated()) return <Navigate to="/game" replace />;

  const [tab, setTab] = useState<"login" | "register">("login");

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-semibold mb-6">Welcome</h1>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <button
          className={`px-3 py-1.5 rounded ${tab === "login" ? "bg-blue-600 text-white" : "bg-gray-200"
            }`}
          onClick={() => setTab("login")}
        >
          Sign In
        </button>
        <button
          className={`px-3 py-1.5 rounded ${tab === "register" ? "bg-blue-600 text-white" : "bg-gray-200"
            }`}
          onClick={() => setTab("register")}
        >
          Create Account
        </button>
      </div>

      {tab === "login" ? (
        <LoginForm
          onSuccess={(user, token) => {
            console.log("[App] Login success, user:", user, "token:", token);
            // כאן אפשר ל-trigger חיבור WS אם רוצים לשלוט ב-VoxelGrid
          }}
          // onDone={() => (window.location.href = "/game")}
          onDone={(user, token) => {
            // שמירת המידע ב-localStorage כדי שנוכל לקרוא בדף ה-game
            localStorage.setItem("token", token);
            localStorage.setItem("user", user);
            navigate("/game")
          }}


        />

        // <LoginForm onDone={() => (window.location.href = "/game")} />
      ) : (
        <RegisterForm onDone={(user, token) => {
          localStorage.setItem("token", token);
          localStorage.setItem("user", user);
          navigate("/game")
        }} />
      )}
    </div>
  );
}

export default function App() {
  const isAuthed = authStorage.isAuthenticated();

  return (
    <BrowserRouter>
      <TopBar />
      <Routes>
        <Route
          path="/"
          element={<Navigate to={isAuthed ? "/game" : "/auth"} replace />}
        />
        <Route path="/auth" element={<AuthPage />} />
        <Route
          path="/game"
          element={
            // <PrivateRoute>
              <GamePage />
            // </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}


