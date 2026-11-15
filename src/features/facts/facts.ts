/** Confirmed facts for the "Just the facts" view, from the PRD and the selected resume. */
export const facts = {
  name: 'Kushal Gaddam',
  role: 'Software Engineer',
  /** Served unchanged from public/resume.pdf. */
  resumeHref: 'resume.pdf',
  resumeFileName: 'Kushal-Gaddam-resume.pdf',
  contacts: [
    { label: 'Email', text: 'Kushalgaddam171@gmail.com', href: 'mailto:Kushalgaddam171@gmail.com' },
    { label: 'Phone', text: '(850) 518-5547', href: 'tel:+18505185547' },
    { label: 'LinkedIn', text: 'linkedin.com/in/kg15', href: 'https://www.linkedin.com/in/kg15' },
    { label: 'GitHub', text: 'github.com/Kushal0217', href: 'https://github.com/Kushal0217' },
  ],
} as const;
