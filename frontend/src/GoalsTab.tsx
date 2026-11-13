import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Group, NumberInput, Paper, Progress, SimpleGrid, Stack, Switch, Text, TextInput, Textarea } from '@mantine/core'
import { IconPlus, IconTargetArrow } from '@tabler/icons-react'
import { DateField, EmptyState, ErrorBanner, Field, LoadingSpinner, Modal, useT } from '@hubra/plugin-sdk'
import { QK, errorText, formatDay, listGoals, saveGoal, type Goal, type Options } from './api'
import { CategoryField, chf, useAction } from './common'

export function GoalProgress({ goal, size = 'lg' }: { goal: Goal; size?: 'md' | 'lg' | 'xl' }) {
  const { t } = useT()
  return (
    <div>
      <Group justify="space-between" mb={4} wrap="nowrap">
        <Text fw={700}>{chf(goal.raised)}</Text>
        <Text size="sm" c="dimmed">
          {t('supporters.goals.of', { target: chf(goal.target) })}
        </Text>
      </Group>
      <Progress value={Math.min(goal.percent, 100)} size={size} radius="xl" color={goal.percent >= 100 ? 'green' : 'violet'} />
      <Group justify="space-between" mt={4}>
        <Text size="xs" c="dimmed">
          {t('supporters.goals.donors', { count: goal.donors })}
        </Text>
        <Text size="xs" c="dimmed">
          {goal.percent}%
        </Text>
      </Group>
    </div>
  )
}

export function GoalBadge({ goal }: { goal: Goal }) {
  const { t } = useT()
  if (goal.percent >= 100)
    return (
      <Badge variant="light" color="green" style={{ textTransform: 'none', flexShrink: 0 }}>
        {t('supporters.goals.reached')}
      </Badge>
    )
  if (!goal.open)
    return (
      <Badge variant="light" color="gray" style={{ textTransform: 'none', flexShrink: 0 }}>
        {t('supporters.goals.closed')}
      </Badge>
    )
  if (goal.endsOn)
    return (
      <Badge variant="light" color="violet" style={{ textTransform: 'none', flexShrink: 0 }}>
        {t('supporters.goals.until', { date: formatDay(goal.endsOn) })}
      </Badge>
    )
  return null
}

export function GoalsTab({ options }: { options: Options | undefined }) {
  const { t } = useT()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const goals = useQuery({ queryKey: QK.goals, queryFn: listGoals })
  const [adding, setAdding] = useState(false)
  const manage = !!options?.can.goals

  return (
    <Stack gap="md">
      <Group justify="space-between" wrap="wrap">
        <Text size="sm" c="dimmed">
          {t('supporters.goals.hint')}
        </Text>
        {manage && (
          <Button leftSection={<IconPlus size={16} />} onClick={() => setAdding(true)}>
            {t('supporters.goals.new')}
          </Button>
        )}
      </Group>
      {goals.error ? (
        <ErrorBanner message={errorText(goals.error)} onRetry={() => goals.refetch()} />
      ) : goals.isLoading ? (
        <LoadingSpinner />
      ) : !goals.data?.length ? (
        <EmptyState icon={<IconTargetArrow size={28} />} title={t('supporters.goals.none')} description={manage ? t('supporters.goals.noneHint') : undefined} />
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
          {goals.data.map((g) => (
            <Paper
              key={g.id}
              withBorder
              p="md"
              radius="md"
              style={{ cursor: 'pointer', opacity: g.open ? 1 : 0.7 }}
              onClick={() => navigate(`/app/supporters/goals/${g.id}`)}
            >
              <Group justify="space-between" align="flex-start" wrap="nowrap" mb="sm">
                <Text fw={600}>{g.title}</Text>
                <GoalBadge goal={g} />
              </Group>
              <GoalProgress goal={g} size="md" />
            </Paper>
          ))}
        </SimpleGrid>
      )}
      {adding && (
        <GoalModal
          goal={null}
          options={options}
          onClose={() => setAdding(false)}
          onDone={(g) => {
            qc.invalidateQueries({ queryKey: QK.all })
            navigate(`/app/supporters/goals/${g.id}`)
          }}
        />
      )}
    </Stack>
  )
}

export function GoalModal({
  goal,
  options,
  onClose,
  onDone,
}: {
  goal: Goal | null
  options: Options | undefined
  onClose: () => void
  onDone: (g: Goal) => void
}) {
  const { t } = useT()
  const { busy, run } = useAction()
  const [title, setTitle] = useState(goal?.title ?? '')
  const [target, setTarget] = useState<number | string>(goal?.target ?? '')
  const [endsOn, setEndsOn] = useState(goal?.endsOn ?? '')
  const [description, setDescription] = useState(goal?.description ?? '')
  const [categoryId, setCategoryId] = useState<number | null>(goal?.categoryId ?? null)
  const [showPublic, setShowPublic] = useState(goal?.showPublic ?? true)

  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    let saved: Goal | undefined
    const ok = await run(async () => {
      saved = await saveGoal({ title, target, endsOn: endsOn || null, description, categoryId, showPublic }, goal?.id)
    }, t('supporters.saved'))
    if (ok && saved) {
      onDone(saved)
      onClose()
    }
  }

  return (
    <Modal
      open
      wide
      onClose={onClose}
      onSubmit={submit}
      title={goal ? t('supporters.goals.edit') : t('supporters.goals.new')}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('supporters.cancel')}
          </Button>
          <Button type="submit" loading={busy} disabled={!title.trim() || target === ''}>
            {t('supporters.save')}
          </Button>
        </>
      }
    >
      <Field label={t('supporters.goals.titleField')}>
        <TextInput value={title} onChange={(e) => setTitle(e.currentTarget.value)} placeholder={t('supporters.goals.example')} data-autofocus />
      </Field>
      <Group grow align="flex-start">
        <Field label={t('supporters.goals.target')}>
          <NumberInput value={target} onChange={setTarget} min={1} decimalScale={2} thousandSeparator="’" prefix="CHF " hideControls />
        </Field>
        <Field label={t('supporters.goals.endsOn')} hint={t('supporters.goals.endsOnHint')}>
          <DateField value={endsOn} onChange={setEndsOn} />
        </Field>
      </Group>
      <Field label={t('supporters.goals.description')}>
        <Textarea value={description} onChange={(e) => setDescription(e.currentTarget.value)} autosize minRows={3} />
      </Field>
      <CategoryField value={categoryId} onChange={setCategoryId} options={options} hint={t('supporters.goals.categoryHint')} />
      <Switch checked={showPublic} onChange={(e) => setShowPublic(e.currentTarget.checked)} label={t('supporters.goals.showPublic')} />
    </Modal>
  )
}
