import { useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ActionIcon, Anchor, Badge, Button, Checkbox, Group, NumberInput, Paper, Select, SimpleGrid, Stack, Text, TextInput, Title } from '@mantine/core'
import { IconArrowLeft, IconHeartHandshake, IconLock, IconLockOpen, IconPencil, IconPlus, IconTrash } from '@tabler/icons-react'
import { ConfirmModal, ErrorBanner, Field, LoadingSpinner, MarkdownRenderer, MemberPicker, Modal, PageHead, useT } from '@hubra/plugin-sdk'
import {
  QK,
  closeGoal,
  deleteDonation,
  deleteGoal,
  errorText,
  formatDay,
  getGoal,
  getOptions,
  pledge,
  recordDonation,
  todayIso,
  type Donation,
  type Goal,
} from './api'
import { chf, useAction } from './common'
import { GoalBadge, GoalModal, GoalProgress } from './GoalsTab'

/** One fundraising goal: progress, giving, and for the board the donations. */
export function GoalScreen() {
  const { t } = useT()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const id = Number(useParams().id)
  const options = useQuery({ queryKey: QK.options, queryFn: getOptions })
  const goal = useQuery({ queryKey: QK.goal(id), queryFn: () => getGoal(id), enabled: id > 0 })
  const [giving, setGiving] = useState(false)
  const [recording, setRecording] = useState(false)
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [dropping, setDropping] = useState<Donation | null>(null)
  const { busy, run } = useAction()
  const manage = !!options.data?.can.goals
  const g = goal.data
  const refresh = () => qc.invalidateQueries({ queryKey: QK.all })

  if (goal.isLoading || options.isLoading) return <LoadingSpinner />
  if (goal.error || !g) return <ErrorBanner message={errorText(goal.error)} onRetry={() => goal.refetch()} />

  const unpaid = (g.mine ?? []).filter((d) => !d.counted)

  return (
    <>
      <PageHead
        back={
          <Anchor component="button" size="sm" onClick={() => navigate('/app/supporters')}>
            <Group gap={4}>
              <IconArrowLeft size={14} /> {t('supporters.tabs.goals')}
            </Group>
          </Anchor>
        }
        title={g.title}
        actions={
          manage ? (
            <Group gap="xs">
              <ActionIcon variant="default" size="lg" aria-label={t('supporters.edit')} onClick={() => setEditing(true)}>
                <IconPencil size={16} />
              </ActionIcon>
              <ActionIcon variant="default" size="lg" aria-label={t('supporters.delete')} onClick={() => setDeleting(true)}>
                <IconTrash size={16} />
              </ActionIcon>
            </Group>
          ) : undefined
        }
      />
      <Stack gap="lg">
        <Paper withBorder p="lg" radius="md">
          <Group justify="space-between" align="flex-start" mb="md" wrap="wrap">
            <GoalBadge goal={g} />
            {g.open && (
              <Button leftSection={<IconHeartHandshake size={16} />} onClick={() => setGiving(true)}>
                {t('supporters.goals.give')}
              </Button>
            )}
          </Group>
          <GoalProgress goal={g} size="xl" />
          {g.pledged > 0 && (
            <Text size="sm" c="dimmed" mt="xs">
              {t('supporters.goals.pledged', { amount: chf(g.pledged) })}
            </Text>
          )}
          {unpaid.length > 0 && (
            <Text size="sm" mt="xs">
              {t('supporters.goals.yourInvoice')}{' '}
              <Anchor component="button" size="sm" onClick={() => navigate('/app/dashboard')}>
                {t('supporters.goals.toInvoices')}
              </Anchor>
            </Text>
          )}
        </Paper>
        {g.description && (
          <Paper withBorder p="md" radius="md">
            <MarkdownRenderer content={g.description} />
          </Paper>
        )}
        <Paper withBorder p="md" radius="md">
          <Group justify="space-between" mb="sm" wrap="wrap">
            <Title order={4}>{t('supporters.goals.donations')}</Title>
            {manage && (
              <Group gap="xs">
                <Button variant="light" leftSection={<IconPlus size={16} />} onClick={() => setRecording(true)}>
                  {t('supporters.goals.record')}
                </Button>
                <Button
                  variant="default"
                  leftSection={g.closed ? <IconLockOpen size={16} /> : <IconLock size={16} />}
                  loading={busy}
                  onClick={() => run(() => closeGoal(g.id, g.closed)).then(refresh)}
                >
                  {g.closed ? t('supporters.goals.reopen') : t('supporters.goals.close')}
                </Button>
              </Group>
            )}
          </Group>
          {!g.donations?.length ? (
            <Text size="sm" c="dimmed">
              {t('supporters.goals.noDonations')}
            </Text>
          ) : (
            <Stack gap={6}>
              {g.donations.map((d) => (
                <Group key={d.id} justify="space-between" wrap="nowrap" align="flex-start">
                  <div style={{ minWidth: 0 }}>
                    <Group gap={6}>
                      <Text size="sm" fw={500}>
                        {d.name ?? t('supporters.goals.anonymous')}
                      </Text>
                      {manage && d.anonymous && (
                        <Badge size="xs" variant="light" color="gray" style={{ textTransform: 'none' }}>
                          {t('supporters.goals.anonymous')}
                        </Badge>
                      )}
                      {!d.counted && (
                        <Badge size="xs" variant="light" color="orange" style={{ textTransform: 'none' }}>
                          {t('supporters.goals.notPaid')}
                        </Badge>
                      )}
                    </Group>
                    <Text size="xs" c="dimmed">
                      {formatDay(d.donatedOn)}
                      {d.message ? ` · ${d.message}` : ''}
                    </Text>
                  </div>
                  <Group gap={4} wrap="nowrap">
                    <Text size="sm" style={{ whiteSpace: 'nowrap' }}>
                      {chf(d.amount)}
                    </Text>
                    {manage && (
                      <ActionIcon variant="subtle" color="red" size="sm" aria-label={t('supporters.delete')} onClick={() => setDropping(d)}>
                        <IconTrash size={14} />
                      </ActionIcon>
                    )}
                  </Group>
                </Group>
              ))}
            </Stack>
          )}
        </Paper>
      </Stack>

      {giving && <GiveModal goal={g} onClose={() => setGiving(false)} onDone={refresh} />}
      {recording && <RecordModal goal={g} onClose={() => setRecording(false)} onDone={refresh} />}
      {editing && <GoalModal goal={g} options={options.data} onClose={() => setEditing(false)} onDone={refresh} />}
      <ConfirmModal
        open={!!dropping}
        title={t('supporters.goals.deleteDonation')}
        body={dropping ? `${dropping.name ?? t('supporters.goals.anonymous')} · ${chf(dropping.amount)}` : ''}
        confirmLabel={t('supporters.delete')}
        onClose={() => setDropping(null)}
        onConfirm={async () => {
          if (dropping) await run(() => deleteDonation(dropping.id))
          setDropping(null)
          refresh()
        }}
      />
      <ConfirmModal
        open={deleting}
        title={t('supporters.goals.deleteTitle')}
        body={t('supporters.goals.deleteBody')}
        confirmLabel={t('supporters.delete')}
        onClose={() => setDeleting(false)}
        onConfirm={async () => {
          if (await run(() => deleteGoal(g.id))) {
            refresh()
            navigate('/app/supporters')
          }
          setDeleting(false)
        }}
      />
    </>
  )
}

const AMOUNTS = [20, 50, 100, 200]

function GiveModal({ goal, onClose, onDone }: { goal: Goal; onClose: () => void; onDone: () => void }) {
  const { t } = useT()
  const { busy, run } = useAction()
  const [amount, setAmount] = useState<number | string>(50)
  const [anonymous, setAnonymous] = useState(false)
  const [message, setMessage] = useState('')
  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    if (await run(() => pledge(goal.id, { amount, anonymous, message }), t('supporters.goals.thanks'))) {
      onDone()
      onClose()
    }
  }
  return (
    <Modal
      open
      onClose={onClose}
      onSubmit={submit}
      title={t('supporters.goals.giveTitle', { title: goal.title })}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('supporters.cancel')}
          </Button>
          <Button type="submit" loading={busy} disabled={!Number(amount)}>
            {t('supporters.goals.giveButton', { amount: chf(Number(amount) || 0) })}
          </Button>
        </>
      }
    >
      <SimpleGrid cols={4} spacing="xs">
        {AMOUNTS.map((a) => (
          <Button key={a} variant={Number(amount) === a ? 'filled' : 'default'} onClick={() => setAmount(a)}>
            {a}
          </Button>
        ))}
      </SimpleGrid>
      <Field label={t('supporters.goals.otherAmount')}>
        <NumberInput value={amount} onChange={setAmount} min={1} max={100000} decimalScale={2} thousandSeparator="’" prefix="CHF " hideControls />
      </Field>
      <Field label={t('supporters.goals.message')}>
        <TextInput value={message} onChange={(e) => setMessage(e.currentTarget.value)} maxLength={500} />
      </Field>
      <Checkbox checked={anonymous} onChange={(e) => setAnonymous(e.currentTarget.checked)} label={t('supporters.goals.beAnonymous')} />
      <Text size="sm" c="dimmed">
        {t('supporters.goals.giveHint')}
      </Text>
    </Modal>
  )
}

function RecordModal({ goal, onClose, onDone }: { goal: Goal; onClose: () => void; onDone: () => void }) {
  const { t } = useT()
  const { busy, run } = useAction()
  const [memberId, setMemberId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [amount, setAmount] = useState<number | string>('')
  const [donatedOn, setDonatedOn] = useState(todayIso())
  const [method, setMethod] = useState('IBAN')
  const [anonymous, setAnonymous] = useState(false)
  const [message, setMessage] = useState('')
  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    if (await run(() => recordDonation(goal.id, { memberId, name, amount, donatedOn, method, anonymous, message }), t('supporters.goals.recorded'))) {
      onDone()
      onClose()
    }
  }
  return (
    <Modal
      open
      onClose={onClose}
      onSubmit={submit}
      title={t('supporters.goals.record')}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('supporters.cancel')}
          </Button>
          <Button type="submit" loading={busy} disabled={!amount || (!memberId && !name.trim())}>
            {t('supporters.goals.recordButton')}
          </Button>
        </>
      }
    >
      <Group grow align="flex-start">
        <Field label={t('supporters.goals.donorName')} hint={t('supporters.goals.donorHint')}>
          <TextInput value={name} onChange={(e) => setName(e.currentTarget.value)} data-autofocus />
        </Field>
        <Field label={t('supporters.goals.orMember')}>
          <MemberPicker aria-label={t('supporters.goals.orMember')} value={memberId} noneLabel="–" onChange={(v) => setMemberId(v ? Number(v) : null)} />
        </Field>
      </Group>
      <Group grow align="flex-start">
        <Field label={t('supporters.amount')}>
          <NumberInput value={amount} onChange={setAmount} min={1} decimalScale={2} thousandSeparator="’" prefix="CHF " hideControls />
        </Field>
        <Field label={t('supporters.goals.donatedOn')}>
          <TextInput type="date" value={donatedOn} onChange={(e) => setDonatedOn(e.currentTarget.value)} />
        </Field>
        <Field label={t('supporters.goals.method')}>
          <Select
            data={['IBAN', 'Cash', 'Twint'].map((m) => ({ value: m, label: t(`supporters.method.${m}`) }))}
            value={method}
            onChange={(m) => m && setMethod(m)}
            allowDeselect={false}
          />
        </Field>
      </Group>
      <Field label={t('supporters.goals.message')}>
        <TextInput value={message} onChange={(e) => setMessage(e.currentTarget.value)} maxLength={500} />
      </Field>
      <Checkbox checked={anonymous} onChange={(e) => setAnonymous(e.currentTarget.checked)} label={t('supporters.goals.keepAnonymous')} />
      <Text size="sm" c="dimmed">
        {t('supporters.goals.recordHint')}
      </Text>
    </Modal>
  )
}
