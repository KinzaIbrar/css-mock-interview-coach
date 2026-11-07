import { useEffect, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronLeft, ChevronRight, Library, Search } from 'lucide-react'
import { getQuestionMeta, listQuestions } from '@/api/content'
import { toApiError } from '@/api/client'
import type { QuestionOut } from '@/api/types'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Alert, EmptyState, ErrorState, Skeleton } from '@/components/ui/Feedback'
import { SelectField, TextInput } from '@/components/ui/Form'
import { titleCase } from '@/utils/format'

const PAGE_SIZE = 10

function useDebounced<T>(value: T, ms = 350): T {
  const [v, setV] = useState(value)
  useEffect(() => { const t = window.setTimeout(() => setV(value), ms); return () => window.clearTimeout(t) }, [value, ms])
  return v
}

function QuestionItem({ q }: { q: QuestionOut }) {
  return (
    <details className="group border-b border-line last:border-0">
      <summary className="flex cursor-pointer list-none items-start gap-3 px-5 py-4 hover:bg-surface-2 [&::-webkit-details-marker]:hidden">
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-ink">{q.text}</span>
          <span className="mt-1.5 flex flex-wrap gap-2">
            <Badge>{q.subject}</Badge><Badge>{q.topic}</Badge>
            <Badge tone={q.difficulty === 'hard' ? 'warning' : q.difficulty === 'medium' ? 'primary' : 'success'}>{titleCase(q.difficulty)}</Badge>
          </span>
        </span>
        <ChevronDown className="mt-1 size-4 shrink-0 text-muted transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="space-y-4 bg-surface-2 px-5 py-4 text-sm">
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Reference answer {q.is_sample && '(unverified sample)'}</h4>
          <p className="mt-1.5 whitespace-pre-wrap text-ink-2">{q.reference_answer}</p>
        </div>
        {q.explanation && <div><h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Why it is asked</h4><p className="mt-1.5 text-ink-2">{q.explanation}</p></div>}
        {q.evaluation_criteria.length > 0 && (
          <div><h4 className="text-xs font-semibold uppercase tracking-wide text-muted">What a strong answer shows</h4>
            <ul className="mt-1.5 list-disc space-y-1 pl-5 text-ink-2">{q.evaluation_criteria.map((c) => <li key={c}>{c}</li>)}</ul></div>
        )}
        {q.keywords.length > 0 && (
          <div><h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Key concepts</h4>
            <div className="mt-1.5 flex flex-wrap gap-1.5">{q.keywords.map((k) => <Badge key={k} tone="primary">{k}</Badge>)}</div></div>
        )}
      </div>
    </details>
  )
}

export default function QuestionBank() {
  const [subject, setSubject] = useState('')
  const [difficulty, setDifficulty] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [page, setPage] = useState(0)
  const search = useDebounced(searchInput.trim())

  const meta = useQuery({ queryKey: ['question-meta'], queryFn: getQuestionMeta, staleTime: 5 * 60_000 })
  const list = useQuery({
    queryKey: ['questions', subject, difficulty, search, page],
    queryFn: () => listQuestions({ subject, difficulty, search, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    placeholderData: keepPreviousData,
  })
  const total = list.data?.total ?? 0
  const from = total === 0 ? 0 : page * PAGE_SIZE + 1
  const to = Math.min(total, (page + 1) * PAGE_SIZE)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[1.75rem] font-semibold">Question bank</h1>
        <p className="mt-1 text-sm text-muted">Browse the practice questions with reference answers. Search results are ranked by relevance.</p>
      </div>
      <Alert tone="info" live="off" title="Sample, unverified study aids">
        {list.data?.notice ?? meta.data?.notice ?? 'Questions and reference answers are practice material, not official CSS content.'}
      </Alert>

      <Card>
        <div className="grid gap-4 border-b border-line p-5 sm:grid-cols-3">
          <TextInput
            label="Search" type="search" value={searchInput} placeholder="e.g. Objectives Resolution"
            onChange={(e) => { setSearchInput(e.target.value); setPage(0) }}
            trailing={<Search className="mr-2 size-4 text-muted" aria-hidden />}
          />
          <SelectField label="Subject" value={subject} onChange={(e) => { setSubject(e.target.value); setPage(0) }}>
            <option value="">All subjects</option>
            {meta.data?.subjects.map((s) => <option key={s.subject} value={s.subject}>{s.subject}</option>)}
          </SelectField>
          <SelectField label="Difficulty" value={difficulty} onChange={(e) => { setDifficulty(e.target.value); setPage(0) }}>
            <option value="">All levels</option>
            <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
          </SelectField>
        </div>

        {list.isPending && <div className="space-y-3 p-5" aria-busy="true" aria-label="Loading questions">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>}
        {list.error && !list.data && <ErrorState message={toApiError(list.error).message} onRetry={() => list.refetch()} title="We couldn't load questions" />}
        {list.data && list.data.items.length === 0 && (
          <EmptyState icon={Library} title="No questions match" description="Try a different search or clear a filter." action={<Button variant="secondary" onClick={() => { setSubject(''); setDifficulty(''); setSearchInput(''); setPage(0) }}>Clear filters</Button>} />
        )}
        {list.data && list.data.items.length > 0 && (
          <>
            <div className={list.isFetching ? 'opacity-70 transition-opacity' : 'transition-opacity'}>
              {list.data.items.map((q) => <QuestionItem key={q.id} q={q} />)}
            </div>
            <nav aria-label="Pagination" className="flex items-center justify-between border-t border-line px-4 py-3">
              <Button variant="secondary" size="sm" onClick={() => setPage(page - 1)} disabled={page === 0} icon={<ChevronLeft className="size-4" aria-hidden />}>Previous</Button>
              <span className="text-sm text-muted tabular" aria-live="polite">{from}–{to} of {total}</span>
              <Button variant="secondary" size="sm" onClick={() => setPage(page + 1)} disabled={to >= total} icon={<ChevronRight className="size-4" aria-hidden />}>Next</Button>
            </nav>
          </>
        )}
      </Card>
    </div>
  )
}
