import './App.css'
import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import LandingPage from './pages/LandingPage'
import BrowsePage from './pages/BrowsePage'
import SearchPage from './pages/SearchPage'
import ProductGroupPage from './pages/ProductGroupPage'
import ProductSingletonPage from './pages/ProductSingletonPage'
import NotFoundPage from './pages/NotFoundPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,   // 5 min — data is fresh for 5 minutes
      retry: 1,
    },
  },
})

const router = createBrowserRouter([
  { path: '/', element: <LandingPage /> },
  { path: '/pregled', element: <BrowsePage /> },
  { path: '/kategorija/:slug', element: <Navigate to="/pregled" replace /> },
  { path: '/pretraga', element: <SearchPage /> },
  { path: '/proizvod/g/:matchId', element: <ProductGroupPage /> },
  { path: '/proizvod/:productId', element: <ProductSingletonPage /> },
  { path: '*', element: <NotFoundPage /> },
])

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
