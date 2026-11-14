// The five occasions, copied from the approved design (home-page/index.html).
// Ids must match what the backend validates: interview, pitch, presentation, speech, debate.
//   live       true when Oli talks it through with you by default, false for record mode
//   img        Oli's pose for this occasion (transparent webp in /public)
//   sub        the line under "What are we practicing?"
//   ph         notes field placeholder
//   files      hint next to "Attach files"
//   time / t   length options and the default index
//   aud        audience options
//   role       description under "Talk it through with Oli"
//   start      start button label in live mode
//   lead / q   Oli's opening line and question on the session script
//   part       who Oli plays (used in the live session copy)

export const OCCASIONS = [
  {
    id: 'interview', name: 'Job interview', live: true, img: '/oli-interview.webp',
    sub: 'Oli will play your interviewer and ask follow ups out loud.',
    ph: 'Behavioral interview for a software engineering internship, two people on the panel...',
    files: 'like your resume or the job post',
    time: ['15 minutes', '30 minutes', '45 minutes', '60 minutes'], t: 1,
    aud: ['recruiters', 'a hiring manager', 'a panel', 'a professor'],
    role: 'He asks questions out loud and you answer, like the real thing.',
    start: 'Start interview',
    lead: "I'll be your interviewer today. Answer out loud like it's the real thing.",
    q: 'Tell me a little about yourself and why this role caught your eye.',
    part: 'interviewer',
  },
  {
    id: 'pitch', name: 'Pitch', live: true, img: '/oli-pitch.webp',
    sub: 'Oli will play an investor and push back on anything shaky.',
    ph: 'Three minute demo day pitch for our study app. We end by asking for pilot schools...',
    files: 'like your pitch deck',
    time: ['1 minute', '3 minutes', '5 minutes', '10 minutes'], t: 1,
    aud: ['investors', 'judges', 'customers', 'my class'],
    role: 'He listens like an investor, then asks the hard questions.',
    start: 'Start pitching',
    lead: "I'm an investor with five minutes. Win me over.",
    q: "Go ahead whenever you're ready. I'll jump in when something sounds shaky.",
    part: 'investor',
  },
  {
    id: 'presentation', name: 'Presentation', live: false, img: '/oli-presentation.webp',
    sub: 'Give the whole talk. Oli watches pace, clarity, and eye contact.',
    ph: 'Ten minute class presentation on renewable energy, with slides...',
    files: 'like your slides',
    time: ['5 minutes', '10 minutes', '15 minutes', '20 minutes'], t: 1,
    aud: ['my class', 'a professor', 'coworkers', 'a conference room'],
    role: 'He asks audience style questions when you finish.',
    start: 'Start recording',
    lead: 'Showtime. Give me the whole talk from start to finish.',
    q: "When you finish, I'll show you the two things to fix first.",
    part: 'audience',
  },
  {
    id: 'speech', name: 'Speech or toast', live: false, img: '/oli-speech.webp',
    sub: 'Weddings, graduations, awards. Oli listens like a guest.',
    ph: "Four minute toast at my best friend's wedding. One funny story, one sweet ending...",
    files: 'like your draft',
    time: ['2 minutes', '4 minutes', '6 minutes', '10 minutes'], t: 1,
    aud: ['friends and family', 'graduates', 'coworkers', 'a big crowd'],
    role: 'He reacts like a guest and tells you what he remembers.',
    start: 'Start recording',
    lead: 'Deliver it like the room is full.',
    q: "I'll tell you where it lands and where to slow down.",
    part: 'audience',
  },
  {
    id: 'debate', name: 'Debate', live: true, img: '/oli-debate.webp',
    sub: 'Oli takes the other side and argues back.',
    ph: 'I argue that schools should allow AI tools on homework. Opening, then two rebuttals...',
    files: 'like your notes',
    time: ['3 minutes', '5 minutes', '8 minutes', '12 minutes'], t: 1,
    aud: ['judges', 'my class', 'an opponent', 'an open audience'],
    role: 'He argues the other side, and you rebut.',
    start: 'Start the debate',
    lead: "I'm taking the other side. Make your claim clearly.",
    q: "Give me your opening statement. I'll rebut, then it's your turn.",
    part: 'debate opponent',
  },
]

export const occasionById = Object.fromEntries(OCCASIONS.map((o) => [o.id, o]))

export const occasionFor = (id) => occasionById[id] ?? OCCASIONS[0]

// "30 minutes" -> 30, the backend's time_limit is whole minutes.
export const minutesOf = (label) => parseInt(label, 10) || null

// Files the backend can read (POST /rehearsals/{id}/files).
export const ACCEPTED_FILES = '.pdf,.docx,.pptx,.txt,.md'
export const acceptedFile = (f) => /\.(pdf|docx|pptx|txt|md)$/i.test(f.name)
