import { client, tokenFromResponse } from "./client";
import type { AuthResponse, LoginRequest, RegisterRequest, UpdateProfileRequest, User, UserStats } from "../types/auth";

export const authApi = {
  async register(payload: RegisterRequest): Promise<AuthResponse> {
    const { data } = await client.post<AuthResponse>("/auth/register", payload);
    tokenFromResponse(data.tokens.access_token, data.tokens.refresh_token);
    return data;
  },

  async login(payload: LoginRequest): Promise<AuthResponse> {
    const { data } = await client.post<AuthResponse>("/auth/login", payload);
    tokenFromResponse(data.tokens.access_token, data.tokens.refresh_token);
    return data;
  },

  async me(): Promise<User> {
    const { data } = await client.get<User>("/users/me");
    return data;
  },
};

export const usersApi = {
  async updateProfile(payload: UpdateProfileRequest): Promise<User> {
    const { data } = await client.patch<User>("/users/me", payload);
    return data;
  },

  async stats(): Promise<UserStats> {
    const { data } = await client.get<UserStats>("/users/me/stats");
    return data;
  },

  async changePassword(current_password: string, new_password: string): Promise<void> {
    await client.post("/users/me/password", { current_password, new_password });
  },

  async deleteAccount(password: string): Promise<void> {
    await client.delete("/users/me", { data: { password } });
  },
};