import { useEffect, useState, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ActionIcon,
  Badge,
  Button,
  CopyButton,
  FileButton,
  Group,
  NumberInput,
  Paper,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core'
import { IconCheck, IconCopy, IconPencil, IconPhoto, IconPlus, IconReceipt2, IconTrash, IconWorld } from '@tabler/icons-react'
import { ConfirmModal, EmptyState, ErrorBanner, Field, LoadingSpinner, Modal, useT } from '@hubra/plugin-sdk'
import {
  QK,
  deletePackage,
  deleteSponsor,
  errorText,
  formatDay,
  invoiceSponsors,
  listPackages,
  listSponsors,
  logoUrl,
  removeLogo,
  savePackage,
  saveSponsor,
  uploadLogo,
  type Options,
  type Package,
  type Sponsor,
} from './api'
import { CategoryField, chf, useAction } from './common'

function Logo({ sponsor }: { sponsor: Sponsor }) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    if (!sponsor.hasLogo) return setSrc(null)
    let url: string | null = null
    let alive = true
    logoUrl(sponsor.id)
      .then((u) => {
        url = u
        if (alive) setSrc(u)
      })
      .catch(() => setSrc(null))
    return () => {
      alive = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [sponsor.id, sponsor.hasLogo])
  return (
    <div
      style={{
        width: 64,
        height: 40,
        borderRadius: 6,
        background: 'var(--mantine-color-gray-0)',
        border: '1px solid var(--mantine-color-default-border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        overflow: 'hidden',
      }}
    >
      {src ? <img src={src} alt="" style={{ maxWidth: '90%', maxHeight: '90%' }} /> : <IconPhoto size={18} color="var(--mantine-color-dimmed)" />}
    </div>
  )
}

export function SponsorsTab({ options }: { options: Options | undefined }) {
  const { t } = useT()
  const qc = useQueryClient()
  const sponsors = useQuery({ queryKey: QK.sponsors, queryFn: listSponsors })
  const packages = useQuery({ queryKey: QK.packages, queryFn: listPackages })
  const [form, setForm] = useState<Sponsor | 'new' | null>(null)
  const [deleting, setDeleting] = useState<Sponsor | null>(null)
  const [invoicing, setInvoicing] = useState(false)
  const [packagesOpen, setPackagesOpen] = useState(false)
  const { run } = useAction()
  const canEdit = !!options?.can.sponsors
  const refresh = () => qc.invalidateQueries({ queryKey: QK.all })
  const year = new Date().getFullYear()
  const active = (sponsors.data ?? []).filter((s) => s.active)
  const yearly = active.reduce((sum, s) => sum + (s.yearly ?? 0), 0)
  const due = active.filter((s) => (s.yearly ?? 0) > 0 && s.lastInvoicedYear !== year)

  return (
    <Stack gap="md">
      <Group justify="space-between" wrap="wrap">
        <Text size="sm" c="dimmed">
          {sponsors.data?.length ? t('supporters.sponsors.yearly', { count: active.length, amount: chf(yearly) }) : t('supporters.sponsors.hint')}
        </Text>
        {canEdit && (
          <Group gap="xs">
            <Button variant="default" onClick={() => setPackagesOpen(true)}>
              {t('supporters.packages.title')}
            </Button>
            <Button variant="default" leftSection={<IconReceipt2 size={16} />} disabled={!due.length} onClick={() => setInvoicing(true)}>
              {t('supporters.sponsors.invoice', { year })}
            </Button>
            <Button leftSection={<IconPlus size={16} />} onClick={() => setForm('new')}>
              {t('supporters.sponsors.new')}
            </Button>
          </Group>
        )}
      </Group>
      {sponsors.error ? (
        <ErrorBanner message={errorText(sponsors.error)} onRetry={() => sponsors.refetch()} />
      ) : sponsors.isLoading ? (
        <LoadingSpinner />
      ) : !sponsors.data?.length ? (
        <EmptyState icon={<IconPhoto size={28} />} title={t('supporters.sponsors.none')} description={t('supporters.sponsors.noneHint')} />
      ) : (
        <Table.ScrollContainer minWidth={640}>
          <Table verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('supporters.sponsors.sponsor')}</Table.Th>
                <Table.Th>{t('supporters.sponsors.package')}</Table.Th>
                <Table.Th>{t('supporters.sponsors.perYear')}</Table.Th>
                <Table.Th>{t('supporters.sponsors.invoiced')}</Table.Th>
                {canEdit && <Table.Th />}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {sponsors.data.map((s) => (
                <Table.Tr key={s.id} style={s.active ? undefined : { opacity: 0.55 }}>
                  <Table.Td>
                    <Group gap="sm" wrap="nowrap">
                      <Logo sponsor={s} />
                      <div style={{ minWidth: 0 }}>
                        <Group gap={6} wrap="nowrap">
                          <Text fw={600} size="sm">
                            {s.name}
                          </Text>
                          {s.showPublic && s.active && <IconWorld size={14} color="var(--mantine-color-dimmed)" aria-label={t('supporters.sponsors.public')} />}
                        </Group>
                        <Text size="xs" c="dimmed">
                          {[s.contactName, s.until ? t('supporters.sponsors.until', { date: formatDay(s.until) }) : null].filter(Boolean).join(' · ')}
                        </Text>
                      </div>
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    {s.packageName ? (
                      <Badge variant="light" color="violet" style={{ textTransform: 'none' }}>
                        {s.packageName}
                      </Badge>
                    ) : (
                      '–'
                    )}
                  </Table.Td>
                  <Table.Td style={{ whiteSpace: 'nowrap' }}>{s.yearly != null ? chf(s.yearly) : '–'}</Table.Td>
                  <Table.Td>
                    {s.lastInvoicedYear === year ? (
                      <Badge variant="light" color="green" style={{ textTransform: 'none' }}>
                        {year}
                      </Badge>
                    ) : s.active && s.yearly ? (
                      <Badge variant="light" color="orange" style={{ textTransform: 'none' }}>
                        {t('supporters.sponsors.notYet')}
                      </Badge>
                    ) : (
                      '–'
                    )}
                  </Table.Td>
                  {canEdit && (
                    <Table.Td>
                      <Group gap={4} wrap="nowrap" justify="flex-end">
                        <ActionIcon variant="subtle" color="gray" onClick={() => setForm(s)} aria-label={t('supporters.edit')}>
                          <IconPencil size={16} />
                        </ActionIcon>
                        <ActionIcon variant="subtle" color="red" onClick={() => setDeleting(s)} aria-label={t('supporters.delete')}>
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Group>
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {options?.publicUrl && (
        <Paper withBorder p="sm" radius="md">
          <Group justify="space-between" wrap="nowrap" gap="sm">
            <div style={{ minWidth: 0 }}>
              <Text size="sm" fw={600}>
                {t('supporters.sponsors.forWebsite')}
              </Text>
              <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>
                {options.publicUrl}
              </Text>
            </div>
            <CopyButton value={options.publicUrl}>
              {({ copied, copy }) => (
                <ActionIcon variant="default" onClick={copy} aria-label={t('supporters.copy')}>
                  {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                </ActionIcon>
              )}
            </CopyButton>
          </Group>
        </Paper>
      )}
      {form && <SponsorModal sponsor={form === 'new' ? null : form} packages={packages.data ?? []} onClose={() => setForm(null)} onDone={refresh} />}
      {invoicing && <InvoiceModal options={options} year={year} count={due.length} onClose={() => setInvoicing(false)} onDone={refresh} />}
      {packagesOpen && <PackagesModal packages={packages.data ?? []} onClose={() => setPackagesOpen(false)} onDone={refresh} />}
      <ConfirmModal
        open={!!deleting}
        title={t('supporters.sponsors.deleteTitle')}
        body={deleting?.name ?? ''}
        confirmLabel={t('supporters.delete')}
        onClose={() => setDeleting(null)}
        onConfirm={async () => {
          if (deleting) await run(() => deleteSponsor(deleting.id))
          setDeleting(null)
          refresh()
        }}
      />
    </Stack>
  )
}

function SponsorModal({ sponsor, packages, onClose, onDone }: { sponsor: Sponsor | null; packages: Package[]; onClose: () => void; onDone: () => void }) {
  const { t } = useT()
  const { busy, run } = useAction()
  const [v, setV] = useState({
    name: sponsor?.name ?? '',
    contactName: sponsor?.contactName ?? '',
    email: sponsor?.email ?? '',
    phone: sponsor?.phone ?? '',
    website: sponsor?.website ?? '',
    street: sponsor?.street ?? '',
    postalCode: sponsor?.postalCode ?? '',
    city: sponsor?.city ?? '',
    since: sponsor?.since ?? '',
    until: sponsor?.until ?? '',
    notes: sponsor?.notes ?? '',
  })
  const [packageId, setPackageId] = useState<number | null>(sponsor?.packageId ?? packages[0]?.id ?? null)
  const [amount, setAmount] = useState<number | string>(sponsor?.amount ?? '')
  const [showPublic, setShowPublic] = useState(sponsor?.showPublic ?? true)
  const [logo, setLogo] = useState<File | null>(null)
  const set = (key: keyof typeof v, value: string) => setV((old) => ({ ...old, [key]: value }))

  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    const ok = await run(async () => {
      const saved = await saveSponsor(
        { ...v, since: v.since || null, until: v.until || null, packageId, amount: amount === '' ? null : amount, showPublic },
        sponsor?.id,
      )
      if (logo) await uploadLogo(saved.id, logo)
    }, t('supporters.saved'))
    if (ok) {
      onDone()
      onClose()
    }
  }

  return (
    <Modal
      open
      wide
      onClose={onClose}
      onSubmit={submit}
      title={sponsor ? t('supporters.sponsors.edit') : t('supporters.sponsors.new')}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('supporters.cancel')}
          </Button>
          <Button type="submit" loading={busy} disabled={!v.name.trim()}>
            {t('supporters.save')}
          </Button>
        </>
      }
    >
      <Group grow align="flex-start">
        <Field label={t('supporters.name')}>
          <TextInput value={v.name} onChange={(e) => set('name', e.currentTarget.value)} placeholder={t('supporters.sponsors.example')} data-autofocus />
        </Field>
        <Field label={t('supporters.sponsors.website')}>
          <TextInput value={v.website} onChange={(e) => set('website', e.currentTarget.value)} placeholder="www.example.ch" />
        </Field>
      </Group>
      <Group grow align="flex-start">
        <Field label={t('supporters.sponsors.package')}>
          <Select
            data={packages.map((p) => ({ value: String(p.id), label: `${p.name} · ${chf(p.amount)}` }))}
            value={packageId ? String(packageId) : null}
            onChange={(id) => setPackageId(id ? Number(id) : null)}
            placeholder={t('supporters.sponsors.noPackage')}
            clearable
          />
        </Field>
        <Field label={t('supporters.sponsors.ownAmount')} hint={t('supporters.sponsors.ownAmountHint')}>
          <NumberInput value={amount} onChange={setAmount} min={0} leftSection="CHF" leftSectionWidth={44} />
        </Field>
      </Group>
      <Group grow align="flex-start">
        <Field label={t('supporters.sponsors.since')}>
          <TextInput type="date" value={v.since} onChange={(e) => set('since', e.currentTarget.value)} />
        </Field>
        <Field label={t('supporters.sponsors.untilField')}>
          <TextInput type="date" value={v.until} onChange={(e) => set('until', e.currentTarget.value)} />
        </Field>
      </Group>
      <Group grow align="flex-start">
        <Field label={t('supporters.sponsors.contact')}>
          <TextInput value={v.contactName} onChange={(e) => set('contactName', e.currentTarget.value)} />
        </Field>
        <Field label={t('supporters.sponsors.email')}>
          <TextInput type="email" value={v.email} onChange={(e) => set('email', e.currentTarget.value)} />
        </Field>
        <Field label={t('supporters.sponsors.phone')}>
          <TextInput value={v.phone} onChange={(e) => set('phone', e.currentTarget.value)} />
        </Field>
      </Group>
      <Group grow align="flex-start">
        <Field label={t('supporters.sponsors.street')}>
          <TextInput value={v.street} onChange={(e) => set('street', e.currentTarget.value)} />
        </Field>
        <Field label={t('supporters.sponsors.postalCode')}>
          <TextInput value={v.postalCode} onChange={(e) => set('postalCode', e.currentTarget.value)} />
        </Field>
        <Field label={t('supporters.sponsors.city')}>
          <TextInput value={v.city} onChange={(e) => set('city', e.currentTarget.value)} />
        </Field>
      </Group>
      <Field label={t('supporters.sponsors.logo')} hint={t('supporters.sponsors.logoHint')}>
        <Group gap="xs">
          <FileButton onChange={setLogo} accept="image/png,image/jpeg,image/webp,image/svg+xml,image/gif">
            {(props) => (
              <Button variant="default" leftSection={<IconPhoto size={16} />} {...props}>
                {logo ? logo.name : sponsor?.hasLogo ? t('supporters.sponsors.replaceLogo') : t('supporters.sponsors.pickLogo')}
              </Button>
            )}
          </FileButton>
          {sponsor?.hasLogo && !logo && (
            <Button variant="subtle" color="red" onClick={() => run(() => removeLogo(sponsor.id)).then(onDone)}>
              {t('supporters.sponsors.removeLogo')}
            </Button>
          )}
        </Group>
      </Field>
      <Field label={t('supporters.notes')}>
        <Textarea value={v.notes} onChange={(e) => set('notes', e.currentTarget.value)} autosize minRows={2} />
      </Field>
      <Switch checked={showPublic} onChange={(e) => setShowPublic(e.currentTarget.checked)} label={t('supporters.sponsors.showPublic')} />
    </Modal>
  )
}

function InvoiceModal({ options, year, count, onClose, onDone }: { options: Options | undefined; year: number; count: number; onClose: () => void; onDone: () => void }) {
  const { t } = useT()
  const { busy, run } = useAction()
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [dueDays, setDueDays] = useState<number | string>(30)
  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    if (await run(() => invoiceSponsors({ year, categoryId, dueDays: Number(dueDays) || 30 }), t('supporters.sponsors.invoicedToast', { count }))) {
      onDone()
      onClose()
    }
  }
  return (
    <Modal
      open
      onClose={onClose}
      onSubmit={submit}
      title={t('supporters.sponsors.invoice', { year })}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('supporters.cancel')}
          </Button>
          <Button type="submit" loading={busy}>
            {t('supporters.sponsors.invoiceButton', { count })}
          </Button>
        </>
      }
    >
      <Text size="sm">{t('supporters.sponsors.invoiceBody', { count, year })}</Text>
      <Group grow align="flex-start">
        <CategoryField value={categoryId} onChange={setCategoryId} options={options} />
        <Field label={t('supporters.dueDays')}>
          <NumberInput value={dueDays} onChange={setDueDays} min={0} max={365} />
        </Field>
      </Group>
    </Modal>
  )
}

function PackagesModal({ packages, onClose, onDone }: { packages: Package[]; onClose: () => void; onDone: () => void }) {
  const { t } = useT()
  const { busy, run } = useAction()
  const [editing, setEditing] = useState<Package | 'new' | null>(packages.length ? null : 'new')
  const [name, setName] = useState('')
  const [amount, setAmount] = useState<number | string>('')
  const [benefits, setBenefits] = useState('')
  const start = (p: Package | 'new') => {
    setEditing(p)
    setName(p === 'new' ? '' : p.name)
    setAmount(p === 'new' ? '' : p.amount)
    setBenefits(p === 'new' ? '' : (p.benefits ?? ''))
  }
  const save = async () => {
    if (await run(() => savePackage({ name, amount, benefits }, editing === 'new' ? undefined : editing?.id), t('supporters.saved'))) {
      setEditing(null)
      onDone()
    }
  }
  return (
    <Modal open wide onClose={onClose} title={t('supporters.packages.title')} footer={<Button onClick={onClose}>{t('supporters.done')}</Button>}>
      <Text size="sm" c="dimmed">
        {t('supporters.packages.hint')}
      </Text>
      <Stack gap="xs">
        {packages.map((p) => (
          <Paper key={p.id} withBorder p="sm" radius="md">
            <Group justify="space-between" wrap="nowrap">
              <div>
                <Text fw={600}>
                  {p.name} · {chf(p.amount)}
                </Text>
                {p.benefits && (
                  <Text size="sm" c="dimmed">
                    {p.benefits}
                  </Text>
                )}
              </div>
              <Group gap={4} wrap="nowrap">
                <ActionIcon variant="subtle" color="gray" onClick={() => start(p)} aria-label={t('supporters.edit')}>
                  <IconPencil size={16} />
                </ActionIcon>
                <ActionIcon variant="subtle" color="red" onClick={() => run(() => deletePackage(p.id)).then(onDone)} aria-label={t('supporters.delete')}>
                  <IconTrash size={16} />
                </ActionIcon>
              </Group>
            </Group>
          </Paper>
        ))}
      </Stack>
      {editing ? (
        <Paper withBorder p="sm" radius="md">
          <Title order={5} mb="xs">
            {editing === 'new' ? t('supporters.packages.new') : t('supporters.packages.edit')}
          </Title>
          <Group grow align="flex-start">
            <Field label={t('supporters.name')}>
              <TextInput value={name} onChange={(e) => setName(e.currentTarget.value)} placeholder={t('supporters.packages.example')} />
            </Field>
            <Field label={t('supporters.packages.amount')}>
              <NumberInput value={amount} onChange={setAmount} min={0} leftSection="CHF" leftSectionWidth={44} />
            </Field>
          </Group>
          <Field label={t('supporters.packages.benefits')}>
            <Textarea value={benefits} onChange={(e) => setBenefits(e.currentTarget.value)} autosize minRows={2} placeholder={t('supporters.packages.benefitsExample')} />
          </Field>
          <Group justify="flex-end" mt="xs">
            <Button variant="default" onClick={() => setEditing(null)}>
              {t('supporters.cancel')}
            </Button>
            <Button loading={busy} disabled={!name.trim() || amount === ''} onClick={save}>
              {t('supporters.save')}
            </Button>
          </Group>
        </Paper>
      ) : (
        <Button variant="light" leftSection={<IconPlus size={16} />} onClick={() => start('new')} style={{ alignSelf: 'flex-start' }}>
          {t('supporters.packages.new')}
        </Button>
      )}
    </Modal>
  )
}
