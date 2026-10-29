import { useEffect, useRef, useState } from 'react'
import Plot from 'react-plotly.js'
import { useStore } from '@/store'
import { api } from '@/lib/api'

interface EquityChartProps {
  accountId: string | null
}

export function EquityChart({ accountId }: EquityChartProps) {
  const [chartData, setChartData] = useState<any[]>([])
  const [layout, setLayout] = useState<any>({
    template: 'plotly_dark',
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e4e6eb', family: 'Inter, sans-serif' },
    margin: { t: 10, r: 10, b: 40, l: 50 },
    xaxis: {
      gridcolor: 'rgba(255,255,255,0.05)',
      zerolinecolor: 'rgba(255,255,255,0.1)',
      showgrid: true,
    },
    yaxis: {
      gridcolor: 'rgba(255,255,255,0.05)',
      zerolinecolor: 'rgba(255,255,255,0.1)',
      showgrid: true,
      tickformat: '$,.0f',
    },
    hovermode: 'x unified',
    legend: { orientation: 'h', y: -0.15 },
  })
  const [loading, setLoading] = useState(false)
  const plotRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (accountId) {
      loadEquityData()
    }
  }, [accountId])

  const loadEquityData = async () => {
    // In a real app, this would fetch from the API
    // For now, generate mock data
    generateMockData()
  }

  const generateMockData = () => {
    const now = new Date()
    const timestamps: Date[] = []
    const equity: number[] = []
    const benchmark: number[] = []

    let equityValue = 100000
    let benchValue = 100000

    for (let i = 30; i >= 0; i--) {
      const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000)
      timestamps.push(date)

      // Simulate equity curve
      const dailyReturn = (Math.random() - 0.48) * 0.03
      equityValue *= (1 + dailyReturn)
      equity.push(equityValue)

      // Simulate benchmark (BTC)
      const benchReturn = (Math.random() - 0.5) * 0.04
      benchValue *= (1 + benchReturn)
      benchmark.push(benchValue)
    }

    const traces = [
      {
        x: timestamps,
        y: equity,
        type: 'scatter',
        mode: 'lines',
        name: 'Strategy',
        line: { color: '#5c6ffb', width: 2 },
        hovertemplate: '%{x|%b %d}<br>Equity: $%{y:,.0f}<extra></extra>',
      },
      {
        x: timestamps,
        y: benchmark,
        type: 'scatter',
        mode: 'lines',
        name: 'BTC Benchmark',
        line: { color: '#e94560', width: 1.5, dash: 'dot' },
        hovertemplate: '%{x|%b %d}<br>Benchmark: $%{y:,.0f}<extra></extra>',
      },
    ]

    setChartData(traces)
  }

  if (!accountId) {
    return (
      <div className="h-[400px] flex items-center justify-center bg-dark-card rounded-xl border border-dark-border">
        <div className="text-center text-dark-muted">
          <svg className="w-12 h-12 mx-auto mb-4 text-dark-border" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <p className="text-dark-muted">Select an account to view equity curve</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-[400px]" ref={plotRef}>
      <Plot
        data={chartData}
        layout={layout}
        config={{
          displayModeBar: true,
          modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d', 'autoScale2d'],
          displaylogo: false,
          responsive: true,
        }}
        useResizeHandler={true}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  )
}