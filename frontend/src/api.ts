import { apiFetch, apiFetchRaw } from '@hubra/plugin-sdk'

export interface Options {
  can: { sponsorsRead: boolean; sponsors: boolean; goals: boolean }
  memberId: number
  publicUrl?: string
  categories?: { id: number; name: string }[]
}

export interface Package {
  id: number
  name: string
  amount: number
  benefits: string | null
  position: number
}

export interface Sponsor {
  id: number
  name: string
  contactName: string | null
  email: string | null
  phone: string | null
  website: string | null
  street: string | null
  postalCode: string | null
  city: string | null
  packageId: number | null
  packageName: string | null
  amount: number | null
  yearly: number | null
  since: string | null
  until: string | null
  active: boolean
  showPublic: boolean
  hasLogo: boolean
  notes: string | null
  lastInvoicedYear: number | null
  lastInvoiceId: number | null
}

export interface Donation {
  id: number
  name: string | null
  anonymous: boolean
  amount: number
  donatedOn: string
  message: string | null
  counted: boolean
  pledge: boolean
  memberId?: number | null
  invoiceId?: number | null
}

export interface Goal {
  id: number
  title: string
  description: string | null
  target: number
  raised: number
  pledged: number
  percent: number
  donors: number
  endsOn: string | null
  categoryId: number | null
  showPublic: boolean
  closed: boolean
  open: boolean
  donations?: Donation[]
  mine?: Donation[]
}

const BASE = '/app/supporters'
const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const QK = {
  all: ['supporters'] as const,
  options: ['supporters', 'options'] as const,
  packages: ['supporters', 'packages'] as const,
  sponsors: ['supporters', 'sponsors'] as const,
  goals: ['supporters', 'goals'] as const,
  goal: (id: number) => ['supporters', 'goal', id] as const,
  logo: (id: number, v: string) => ['supporters', 'logo', id, v] as const,
}

export const getOptions = () => apiFetch<Options>(`${BASE}/options`)

export const listPackages = () => apiFetch<Package[]>(`${BASE}/packages`)
export const savePackage = (body: Record<string, unknown>, id?: number) =>
  apiFetch<Package>(id ? `${BASE}/packages/${id}` : `${BASE}/packages`, json(id ? 'PATCH' : 'POST', body))
export const deletePackage = (id: number) => apiFetch<void>(`${BASE}/packages/${id}`, { method: 'DELETE' })

export const listSponsors = () => apiFetch<Sponsor[]>(`${BASE}/sponsors`)
export const saveSponsor = (body: Record<string, unknown>, id?: number) =>
  apiFetch<Sponsor>(id ? `${BASE}/sponsors/${id}` : `${BASE}/sponsors`, json(id ? 'PATCH' : 'POST', body))
export const deleteSponsor = (id: number) => apiFetch<void>(`${BASE}/sponsors/${id}`, { method: 'DELETE' })
export async function uploadLogo(id: number, file: File) {
  const form = new FormData()
  form.append('logo', file)
  const res = await apiFetchRaw(`${BASE}/sponsors/${id}/logo`, { method: 'PUT', body: form })
  return (await res.json()) as Sponsor
}
export const removeLogo = (id: number) => apiFetch<Sponsor>(`${BASE}/sponsors/${id}/logo`, { method: 'DELETE' })
export async function logoUrl(id: number) {
  const res = await apiFetchRaw(`${BASE}/sponsors/${id}/logo`)
  return URL.createObjectURL(await res.blob())
}
export const invoiceSponsors = (body: { year: number; sponsorIds?: number[]; categoryId?: number | null; dueDays?: number }) =>
  apiFetch<{ invoiced: number[]; skipped: number[]; year: number }>(`${BASE}/sponsors/invoice`, json('POST', body))

export const listGoals = () => apiFetch<Goal[]>(`${BASE}/goals`)
export const getGoal = (id: number) => apiFetch<Goal>(`${BASE}/goals/${id}`)
export const saveGoal = (body: Record<string, unknown>, id?: number) =>
  apiFetch<Goal>(id ? `${BASE}/goals/${id}` : `${BASE}/goals`, json(id ? 'PATCH' : 'POST', body))
export const deleteGoal = (id: number) => apiFetch<void>(`${BASE}/goals/${id}`, { method: 'DELETE' })
export const closeGoal = (id: number, reopen = false) => apiFetch<Goal>(`${BASE}/goals/${id}/close`, json('POST', { reopen }))
export const recordDonation = (id: number, body: Record<string, unknown>) =>
  apiFetch<Donation>(`${BASE}/goals/${id}/donations`, json('POST', body))
export const deleteDonation = (id: number) => apiFetch<void>(`${BASE}/donations/${id}`, { method: 'DELETE' })
export const pledge = (id: number, body: { amount: number | string; anonymous: boolean; message?: string }) =>
  apiFetch<Donation>(`${BASE}/goals/${id}/pledge`, json('POST', body))

export function errorText(err: unknown) {
  return err instanceof Error ? err.message : String(err)
}

export function formatDay(iso: string | null | undefined) {
  if (!iso) return ''
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${d}.${m}.${y}`
}

export function todayIso() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
