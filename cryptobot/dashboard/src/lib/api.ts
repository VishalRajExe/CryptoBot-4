import axios, { AxiosInstance, AxiosError } from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

class ApiClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    })

    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        console.error('API Error:', error.response?.data || error.message)
        return Promise.reject(error)
      }
    )
  }

  // Strategies
  async getStrategies() {
    return this.client.get('/strategies')
  }

  async createStrategy(data: any) {
    return this.client.post('/strategies', data)
  }

  async getStrategy(id: string) {
    return this.client.get(`/strategies/${id}`)
  }

  async updateStrategy(id: string, data: any) {
    return this.client.put(`/strategies/${id}`, data)
  }

  async deleteStrategy(id: string) {
    return this.client.delete(`/strategies/${id}`)
  }

  async generateSignals(data: any) {
    return this.client.post('/strategies/signals', data)
  }

  async runStrategyBacktest(id: string, data: any) {
    return this.client.post(`/strategies/${id}/backtest`, data)
  }

  // Positions
  async getPositions(accountId?: string) {
    const params = accountId ? { account_id: accountId } : {}
    return this.client.get('/positions', { params })
  }

  async getAccountPositions(accountId: string) {
    return this.client.get(`/positions/${accountId}`)
  }

  async getAccountSummary(accountId: string) {
    return this.client.get(`/positions/${accountId}/summary`)
  }

  async closePosition(accountId: string, symbol: string) {
    return this.client.post(`/positions/${accountId}/close/${symbol}`)
  }

  async closeAllPositions(accountId: string) {
    return this.client.post(`/positions/${accountId}/close_all`)
  }

  // Orders
  async getOrders(params?: { account_id?: string; symbol?: string; status?: string }) {
    return this.client.get('/orders', { params })
  }

  async createOrder(data: any) {
    return this.client.post('/orders', data)
  }

  async getOrder(orderId: string, accountId?: string) {
    const params = accountId ? { account_id: accountId } : {}
    return this.client.get(`/orders/${orderId}`, { params })
  }

  async cancelOrder(orderId: string, accountId?: string) {
    const params = accountId ? { account_id: accountId } : {}
    return this.client.delete(`/orders/${orderId}`, { params })
  }

  async cancelAllOrders(accountId?: string, symbol?: string) {
    const params: any = {}
    if (accountId) params.account_id = accountId
    if (symbol) params.symbol = symbol
    return this.client.post('/orders/cancel_all', null, { params })
  }

  async createBracketOrder(data: any) {
    return this.client.post('/orders/bracket', data)
  }

  // Backtest
  async runBacktest(data: any) {
    return this.client.post('/backtest', data)
  }

  async getBacktest(id: string) {
    return this.client.get(`/backtest/${id}`)
  }

  async getBacktestReport(id: string) {
    return this.client.get(`/backtest/${id}/report`, {
      responseType: 'text'
    })
  }

  async optimizeStrategy(data: any) {
    return this.client.post('/backtest/optimize', data)
  }

  async runWalkforward(data: any) {
    return this.client.post('/backtest/walkforward', data)
  }

  async listBacktests() {
    return this.client.get('/backtest')
  }

  async deleteBacktest(id: string) {
    return this.client.delete(`/backtest/${id}`)
  }

  // Research
  async runResearch(data: any) {
    return this.client.post('/research/analyze', data)
  }

  async getResearch(id: string) {
    return this.client.get(`/research/${id}`)
  }

  async listResearch() {
    return this.client.get('/research')
  }

  async getResearchAnalyses(id: string) {
    return this.client.get(`/research/${id}/analyses`)
  }

  async getResearchDebate(id: string) {
    return this.client.get(`/research/${id}/debate`)
  }

  async getResearchMemory(id: string) {
    return this.client.get(`/research/${id}/memory`)
  }

  async settleResearch(id: string) {
    return this.client.post(`/research/${id}/settle`)
  }

  // Settings
  async getSettings() {
    return this.client.get('/settings')
  }

  async updateExchange(name: string, data: any) {
    return this.client.put(`/settings/exchanges/${name}`, data)
  }

  async updateRisk(data: any) {
    return this.client.put('/settings/risk', data)
  }

  async togglePaperTrading(enabled: boolean) {
    return this.client.put('/settings/paper_trading', { enabled })
  }

  async reloadSettings(configPath?: string) {
    return this.client.post('/settings/reload', { config_path: configPath })
  }

  async listExchanges() {
    return this.client.get('/settings/exchanges')
  }

  async getLLMConfig() {
    return this.client.get('/settings/llm')
  }

  async getStrategiesConfig() {
    return this.client.get('/settings/strategies')
  }

  async getRiskConfig() {
    return this.client.get('/settings/risk')
  }

  // Health
  async healthCheck() {
    return this.client.get('/health')
  }
}

export const api = new ApiClient()