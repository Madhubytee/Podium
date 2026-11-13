import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import TopNav from '../components/landing/TopNav'
import Hero from '../components/landing/Hero'
import { FeedbackSample, FinalCall, Footer, HowItWorks, Trust } from '../components/landing/Sections'

export default function Landing() {
  const { hash } = useLocation()
  // Arriving at /#how from another route: scroll to the section once it exists.
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView()
  }, [hash])

  return (
    <div id="landing">
      <TopNav />
      <Hero />
      <HowItWorks />
      <FeedbackSample />
      <Trust />
      <FinalCall />
      <Footer />
    </div>
  )
}
