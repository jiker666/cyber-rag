import request from './request'

export interface UserInfo {
  id: number
  username: string
  nickname: string
  email: string | null
  avatar: string | null
  roleId: number
  roleCode: string
  roleName: string
  status: number
  lastLoginAt: string | null
  createdAt: string
}

export interface LoginPayload {
  username: string
  password: string
}

export interface RegisterPayload {
  username: string
  password: string
  nickname: string
  email?: string
}

export interface LoginResult {
  token: string
  expiresIn: number
  user: UserInfo
}

export function login(payload: LoginPayload): Promise<LoginResult> {
  return request.post('/auth/login', payload)
}

export function register(payload: RegisterPayload): Promise<LoginResult> {
  return request.post('/auth/register', payload)
}

export function fetchProfile(): Promise<UserInfo> {
  return request.get('/auth/me')
}

export function updateProfile(payload: { nickname: string; email?: string; avatar?: string }): Promise<UserInfo> {
  return request.put('/user/profile', payload)
}

export function updatePassword(payload: { oldPassword: string; newPassword: string }): Promise<void> {
  return request.post('/user/password', payload)
}

export interface UserPage {
  records: UserInfo[]
  total: number
  current: number
  size: number
}

export function pageUsers(params: { page: number; size: number; keyword?: string }): Promise<UserPage> {
  return request.get('/admin/users', { params })
}

export function updateUserStatus(id: number, status: number): Promise<void> {
  return request.put(`/admin/users/${id}/status`, { status })
}

export function resetUserPassword(id: number, newPassword: string): Promise<void> {
  return request.post(`/admin/users/${id}/reset-password`, { newPassword })
}
