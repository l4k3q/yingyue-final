<template>
  <div ref="wordCloudChart" class="word-cloud-chart">
    <div class="word-cloud-glow"></div>
  </div>
</template>

<script>
/**
 * WordCloudChart - 科技感词云组件
 * 依赖：Vue 2、ECharts 4、echarts-wordcloud、axios（由使用方全局引入）
 * 数据从后端 /api/screen/keywords 实时拉取，组件内不写死模拟数据
 */
export default {
  name: 'WordCloudChart',
  props: {
    // 后端关键词接口地址
    apiUrl: {
      type: String,
      default: '/api/screen/keywords'
    },
    // 最大关键词数量
    limit: {
      type: Number,
      default: 60
    },
    // 自动刷新间隔（毫秒），0 表示不刷新
    refreshInterval: {
      type: Number,
      default: 30000
    }
  },
  data() {
    return {
      chart: null,
      words: [],
      refreshTimer: null
    };
  },
  mounted() {
    this.$nextTick(() => {
      this.initChart();
      this.loadData();
      this.startAutoRefresh();
    });
    this.resizeHandler = this.debounce(this.resize, 200);
    window.addEventListener('resize', this.resizeHandler);
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.resizeHandler);
    this.stopAutoRefresh();
    if (this.chart) {
      this.chart.dispose();
      this.chart = null;
    }
  },
  methods: {
    // 初始化词云图表
    initChart() {
      const echarts = window.echarts;
      if (!echarts) {
        console.error('WordCloudChart: 未找到全局 echarts');
        return;
      }
      const el = this.$refs.wordCloudChart;
      if (!el || el.clientWidth === 0 || el.clientHeight === 0) {
        setTimeout(() => this.initChart(), 300);
        return;
      }
      this.chart = echarts.init(el);
    },

    // 从后端拉取关键词数据
    async loadData() {
      try {
        const res = await this.httpGet(`${this.apiUrl}?limit=${this.limit}`);
        if (res && res.success && Array.isArray(res.words)) {
          this.words = res.words;
          this.updateChart();
        }
      } catch (err) {
        console.warn('WordCloudChart 获取关键词数据失败：', err);
      }
    },

    // 通用 GET 请求封装
    httpGet(url) {
      return new Promise((resolve, reject) => {
        if (window.axios) {
          window.axios.get(url).then(res => resolve(res.data)).catch(reject);
          return;
        }
        window.fetch(url)
          .then(r => r.json())
          .then(resolve)
          .catch(reject);
      });
    },

    // 渲染/更新词云
    updateChart() {
      if (!this.chart || !this.words.length) return;

      const words = this.words.slice(0, this.limit);
      const maxValue = Math.max(...words.map(w => w.value || 1));
      const totalValue = words.reduce((sum, w) => sum + (w.value || 0), 0);

      // 霓虹渐变配色：根据权重返回不同色相
      const neonPalette = [
        '#00f2ff', // 青
        '#00ff9d', // 青绿
        '#568aea', // 蓝
        '#a855f7', // 紫
        '#ff52b1', // 粉
        '#ff6b6b', // 红
        '#ffd166', // 金黄
        '#06ffa5'  // 荧光绿
      ];

      const getColor = (value) => {
        const ratio = value / maxValue;
        const idx = Math.min(Math.floor(ratio * neonPalette.length), neonPalette.length - 1);
        return neonPalette[neonPalette.length - 1 - idx];
      };

      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          show: true,
          trigger: 'item',
          backgroundColor: 'rgba(11, 15, 30, 0.92)',
          borderColor: 'rgba(86, 138, 234, 0.6)',
          borderWidth: 1,
          padding: [10, 14],
          textStyle: {
            color: '#d3d6dd',
            fontSize: 13
          },
          formatter: (params) => {
            const percent = totalValue ? ((params.value / totalValue) * 100).toFixed(1) : 0;
            return `<div style="font-weight:bold;color:#fff;font-size:15px;margin-bottom:4px">${params.name}</div>
                    <div>出现次数：<span style="color:#50e3c2;font-weight:bold">${params.value}</span></div>
                    <div>占比：<span style="color:#568aea">${percent}%</span></div>`;
          }
        },
        series: [{
          type: 'wordCloud',
          shape: 'circle',
          left: '2%',
          top: '2%',
          width: '96%',
          height: '96%',
          right: null,
          bottom: null,
          sizeRange: [12, 46],
          rotationRange: [-35, 35],
          rotationStep: 10,
          gridSize: 8,
          drawOutOfBound: false,
          layoutAnimation: true,
          textStyle: {
            fontFamily: '"Orbitron", "Rajdhani", "Impact", "Arial Black", "Microsoft YaHei", sans-serif',
            fontWeight: 'bold',
            color: (params) => getColor(params.value),
            textBorderColor: 'rgba(0, 0, 0, 0.7)',
            textBorderWidth: 1,
            textShadowBlur: 12,
            textShadowColor: (params) => getColor(params.value),
            textShadowOffsetX: 0,
            textShadowOffsetY: 0
          },
          emphasis: {
            focus: 'self',
            textStyle: {
              color: '#ffffff',
              textShadowBlur: 22,
              textShadowColor: '#00f2ff',
              textBorderColor: '#00f2ff',
              textBorderWidth: 2,
              shadowBlur: 20,
              shadowColor: 'rgba(0, 242, 255, 0.6)'
            }
          },
          data: words.map(item => ({
            name: item.name,
            value: item.value || 0,
            textStyle: {
              // 为每个词单独设置随机旋转角度，增强错落感
              rotation: this.randomRotation()
            }
          }))
        }]
      };

      this.chart.setOption(option, true);
    },

    // 随机小幅旋转，制造不规则错落感
    randomRotation() {
      const steps = [-25, -15, -8, 0, 8, 15, 25];
      return steps[Math.floor(Math.random() * steps.length)];
    },

    // 窗口自适应
    resize() {
      if (this.chart) {
        this.chart.resize();
      }
    },

    // 启动自动刷新
    startAutoRefresh() {
      if (this.refreshInterval <= 0) return;
      this.stopAutoRefresh();
      this.refreshTimer = setInterval(() => {
        this.loadData();
      }, this.refreshInterval);
    },

    // 停止自动刷新
    stopAutoRefresh() {
      if (this.refreshTimer) {
        clearInterval(this.refreshTimer);
        this.refreshTimer = null;
      }
    },

    debounce(fn, delay) {
      let timer = null;
      return function (...args) {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
      };
    }
  }
};
</script>

<style scoped>
.word-cloud-chart {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  background: radial-gradient(ellipse at center, rgba(16, 24, 48, 0.6) 0%, rgba(9, 10, 15, 0.85) 100%);
  border-radius: 4px;
}

/* 半透明流动光晕背景 */
.word-cloud-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 80%;
  height: 80%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: radial-gradient(circle, rgba(86, 138, 234, 0.18) 0%, transparent 70%);
  filter: blur(20px);
  animation: pulseGlow 4s ease-in-out infinite;
  pointer-events: none;
  z-index: 0;
}

@keyframes pulseGlow {
  0%, 100% {
    opacity: 0.6;
    transform: translate(-50%, -50%) scale(1);
  }
  50% {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1.08);
  }
}

/* echarts 容器层级 */
.word-cloud-chart > div:last-child {
  position: relative;
  z-index: 1;
}
</style>
