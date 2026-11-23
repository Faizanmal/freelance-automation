import type { Metadata } from "next";

type Props = { children: React.ReactNode; params: Promise<{ skill: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { skill } = await params;
  const label = skill.replace(/-/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
  const path = `/freelance-jobs/${encodeURIComponent(skill.toLowerCase())}`;
  const title = `${label} freelance jobs`;
  const description = `Browse public freelance and contract listings tagged for ${label}. Check the original source for current details.`;
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: { title, description, url: path },
    twitter: { card: "summary_large_image", title, description },
  };
}

export default function SkillJobsLayout({ children }: Props) {
  return children;
}
