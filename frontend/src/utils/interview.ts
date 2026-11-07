import type { InterviewDifficulty, InterviewOut, SubjectMeta } from '@/api/types'

/** Completed interviews open their report; unfinished ones resume in the interview room. */
export function interviewLink(i: InterviewOut): string {
  return i.status === 'completed' ? `/interviews/${i.id}/results` : `/interviews/${i.id}`
}

/** How many questions the bank can offer for this choice (null = unknown, let the server decide). */
export function availableQuestions(subject: SubjectMeta | undefined, topic: string, difficulty: InterviewDifficulty): number | null {
  if (!subject) return null
  if (topic) {
    if (difficulty !== 'mixed') return null // the metadata has no topic x difficulty split
    return subject.topics.find((t) => t.topic === topic)?.count ?? 0
  }
  return difficulty === 'mixed' ? subject.count : (subject.difficulties[difficulty] ?? 0)
}
