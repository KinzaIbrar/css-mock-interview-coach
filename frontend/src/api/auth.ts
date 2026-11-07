import { http } from './client'
import type { Health, LoginRequest, RegisterRequest, TokenResponse, User } from './types'

export const register = (body: RegisterRequest) => http.post<TokenResponse>('/auth/register', body).then((r) => r.data)
export const login = (body: LoginRequest) => http.post<TokenResponse>('/auth/login', body).then((r) => r.data)
export const getMe = () => http.get<User>('/auth/me').then((r) => r.data)
export const getHealth = () => http.get<Health>('/health').then((r) => r.data)
