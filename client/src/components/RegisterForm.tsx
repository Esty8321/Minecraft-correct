import React, { useState } from "react";
import { UserPlus, Mail, User, Loader2 } from "lucide-react";
import { authApi, ApiError } from "../utils/api";
import { authStorage } from "../utils/auth";
import { RegisterRequest } from "../types/auth";

interface RegisterFormProps {
  onSuccess?: (user: any) => void;     // called after successful register/login
  onDone?: (user:any, token:string) => void;                 // navigate away if needed
  onSwitchToLogin?: () => void;        // show login screen
}

export default function RegisterForm({
  onSuccess,
  onDone,
  onSwitchToLogin,
}: RegisterFormProps) {
  const [formData, setFormData] = useState<RegisterRequest>({
    username: "",
    email: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.username.trim()) {
      newErrors.username = "Username is required";
    } else if (formData.username.length < 3) {
      newErrors.username = "Username must be at least 3 characters";
    }

    if (!formData.email.trim()) {
      newErrors.email = "Email is setTokenrequired";
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = "Please enter a valid email address";
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
      // 1) Register
      const regRes = await authApi.register(formData);

      // 2) Auto-login (by username to keep it simple)
      const loginRes = await authApi.login({ username: formData.username });

      // 3) Persist session
      authStorage.setToken(loginRes.token);
      authStorage.setUser(loginRes.user);

      // 4) Callbacks
      onSuccess?.(loginRes.user);
      onDone?.();
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.message.includes("username_taken")) {
          setErrors({ username: "Username is already taken" });
        } else if (error.message.includes("email_taken")) {
          setErrors({ email: "Email is already registered" });
        } else {
          setErrors({ general: error.message });
        }
      } else {
        setErrors({ general: "Registration failed. Please try again." });
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

  return (
    <div className="w-full max-w-md">
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full mb-4">
          <UserPlus className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-3xl font-bold text-gray-800 mb-2">Create Account</h2>
        <p className="text-gray-600">Join us today and get started</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {errors.general && (
          <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg text-sm">
            {errors.general}
          </div>
        )}

        {/* Username */}
        <div>
          <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-2">
            Username
          </label>
          <div className="relative">
            <User className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              className={`w-full pl-10 pr-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors ${
                errors.username ? "border-red-300 bg-red-50" : "border-gray-300 bg-white"
              }`}
              placeholder="Enter your username"
              disabled={isLoading}
            />
          </div>
          {errors.username && <p className="mt-1 text-sm text-red-600">{errors.username}</p>}
        </div>

        {/* Email */}
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
            Email Address
          </label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              className={`w-full pl-10 pr-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors ${
                errors.email ? "border-red-300 bg-red-50" : "border-gray-300 bg-white"
              }`}
              placeholder="Enter your email"
              disabled={isLoading}
            />
          </div>
          {errors.email && <p className="mt-1 text-sm text-red-600">{errors.email}</p>}
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-gradient-to-r from-blue-500 to-purple-600 text-white font-semibold py-3 px-4 rounded-lg hover:from-blue-600 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-5 h-5 mr-2 animate-spin" />
              Creating Account...
            </>
          ) : (
            <>
              <UserPlus className="w-5 h-5 mr-2" />
              Create Account
            </>
          )}
        </button>
      </form>

      <div className="mt-6 text-center">
        <p className="text-gray-600">
          Already have an account?{" "}
          <button
            onClick={onSwitchToLogin}
            className="text-blue-600 hover:text-blue-700 font-semibold transition-colors"
          >
            Sign In
          </button>
        </p>
      </div>
    </div>
  );
}
