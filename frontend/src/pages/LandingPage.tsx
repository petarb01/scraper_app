import Navbar from '../components/Navbar'
import Hero from '../components/Hero'
import Stats from '../components/Stats'
import Categories from '../components/Categories'
import FeaturedProducts from '../components/FeaturedProducts'
import HowItWorks from '../components/HowItWorks'
import Footer from '../components/Footer'

export default function LandingPage() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <Stats />
        <Categories />
        <FeaturedProducts />
        <HowItWorks />
      </main>
      <Footer />
    </>
  )
}
