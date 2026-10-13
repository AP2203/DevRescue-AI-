import type { LoginRequest, RegisterRequest } from "../types/auth";

export function validateEmail(email: string): string | null {
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return "Enter a valid email address";
  }
  return null;
}

export function validateUsername(username: string): string | null {
  if (!username || username.length < 3 || username.length > 32) {
    return "Username must be 3-32 characters";
  }
  if (!/^[a-zA-Z0-9_]+$/.test(username)) {
    return "Usernames may only contain letters, numbers and underscores";
  }
  return null;
}

export function validatePassword(password: string): string | null {
  if (!password || password.length < 8) {
    return "Password must be at least 8 characters";
  }
  if (!/[a-z]/.test(password)) return "Add a lowercase letter";
  if (!/[A-Z]/.test(password)) return "Add an uppercase letter";
  if (!/\d/.test(password)) return "Add a digit";
  return null;
}

export function validateRegister(payload: RegisterRequest): Record<string, string> {
  const errors: Record<string, string> = {};
  const email = validateEmail(payload.email);
  const username = validateUsername(payload.username);
  const password = validatePassword(payload.password);
  if (email) errors.email = email;
  if (username) errors.username = username;
  if (password) errors.password = password;
  return errors;
}

export function validateLogin(payload: LoginRequest): Record<string, string> {
  const errors: Record<string, string> = {};
  const email = validateEmail(payload.email);
  if (email) errors.email = email;
  if (!payload.password) errors.password = "Password is required";
  return errors;
}