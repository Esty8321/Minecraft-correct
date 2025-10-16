// src/components/LoginForm.tsx
import React, { useState } from "react";
import { LogIn, Mail, User, Loader2 } from "lucide-react";
import { authApi, ApiError } from "../utils/api";
import { authStorage } from "../utils/auth";
import { LoginRequest } from "../types/auth";

interface LoginFormProps {
  onSuccess?: (user: any, token: string) => void;
  onDone?: (user:any, token:string) => void;
}

type LoginMethod = "username" | "email";

export default function LoginForm({ onSuccess, onDone }: LoginFormProps) {
  const [loginMethod, setLoginMethod] = useState<LoginMethod>("username");
  const [formData, setFormData] = useState({ username: "", email: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (loginMethod === "username") {
      if (!formData.username.trim()) {
        newErrors.username = "Username is required";
      }
    } else {
      if (!formData.email.trim()) {
        newErrors.email = "Email is required";
      } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
        newErrors.email = "Please enter a valid email address";
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setIsLoading(true);
    setErrors({});

    try {
      const loginData: LoginRequest =
        loginMethod === "username"
          ? { username: formData.username }
          : { email: formData.email };

      const response = await authApi.login(loginData);
      console.log("[LoginForm] response token:", response.token);

      if (response.token) {
        // Save token synchronously to storage
        authStorage.setToken(response.token);
        authStorage.setUser(response.user);
        authStorage.setID(response.player_id)
        console.log("[LoginForm] token saved to storage");

        // Callback for any parent logic
        onSuccess?.(response.user, response.token);

        // Navigate internally (no full page refresh)
        onDone?.(response.user, response.token);
      } else {
        setErrors({ general: "No token received from server" });
      }
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.message.includes("user_not_found")) {
          setErrors({
            general: "User not found. Please check your credentials.",
          });
        } else {
          setErrors({ general: error.message });
        }
      } else {
        setErrors({ general: "Login failed. Please try again." });
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: "" }));
  };

  const handleMethodChange = (method: LoginMethod) => {
    setLoginMethod(method);
    setFormData({ username: "", email: "" });
    setErrors({});
  };

  const getInputIcon = () =>
    loginMethod === "username" ? (
      <User className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
    ) : (
      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
    );

  const getInputPlaceholder = () =>
    loginMethod === "username" ? "Enter your username" : "Enter your email";

  return (
    <div className="w-full max-w-md">
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-green-500 to-blue-600 rounded-full mb-4">
          <LogIn className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-3xl font-bold text-gray-800 mb-2">Welcome Back</h2>
        <p className="text-gray-600">Sign in to your account</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6" autoComplete="off">
        {errors.general && (
          <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg text-sm">
            {errors.general}
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Login Method
          </label>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => handleMethodChange("username")}
              className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                loginMethod === "username"
                  ? "bg-blue-100 text-blue-700 border border-blue-300"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              Username
            </button>
            <button
              type="button"
              onClick={() => handleMethodChange("email")}
              className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                loginMethod === "email"
                  ? "bg-blue-100 text-blue-700 border border-blue-300"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              Email
            </button>
          </div>
        </div>

        <div>
          <label
            htmlFor={loginMethod}
            className="block text-sm font-medium text-gray-700 mb-2"
          >
            {loginMethod === "username" ? "Username" : "Email Address"}
          </label>
          <div className="relative">
            {getInputIcon()}
            <input
              type={loginMethod === "email" ? "email" : "text"}
              id={loginMethod}
              name={loginMethod}
              value={formData[loginMethod]}
              onChange={handleChange}
              className={`w-full pl-10 pr-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors ${
                errors[loginMethod] ? "border-red-300 bg-red-50" : "border-gray-300 bg-white"
              }`}
              placeholder={getInputPlaceholder()}
              disabled={isLoading}
              autoComplete="off"
            />
          </div>
          {errors[loginMethod] && (
            <p className="mt-1 text-sm text-red-600">{errors[loginMethod]}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-gradient-to-r from-green-500 to-blue-600 text-white font-semibold py-3 px-4 rounded-lg hover:from-green-600 hover:to-blue-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-5 h-5 mr-2 animate-spin" />
              Signing In...
            </>
          ) : (
            <>
              <LogIn className="w-5 h-5 mr-2" />
              Sign In
            </>
          )}
        </button>
      </form>
    </div>
  );
}
