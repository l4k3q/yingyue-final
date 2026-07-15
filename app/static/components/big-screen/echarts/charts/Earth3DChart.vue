<template>
  <div ref="earthChart" class="earth-chart"></div>
</template>

<script>
/**
 * Earth3DChart - 3D 地球可视化组件
 * 依赖：Vue 2、ECharts 4、ECharts-GL、axios（由使用方全局引入）
 * 全部数据从后端接口获取，禁止在组件内写死模拟数据
 */
export default {
  name: 'Earth3DChart',
  props: {
    // 海陆纹理贴图（本地静态资源路径或网络 URL）
    textureUrl: {
      type: String,
      default: '/static/img/earth/world.topo.bathy.200401.jpg'
    },
    // 高程纹理贴图
    heightTextureUrl: {
      type: String,
      default: '/static/img/earth/bathymetry_bw_composite_4k.jpg'
    },
    // 世界地图 GeoJSON（用于绘制国界）
    geoJsonUrl: {
      type: String,
      default: '/static/data/world.json'
    },
    // 后端经纬度资讯接口
    apiUrl: {
      type: String,
      default: '/api/screen/geo'
    },
    // 是否显示星空背景
    starBackground: {
      type: Boolean,
      default: true
    }
  },
  data() {
    return {
      chart: null,
      geoData: { points: [], lines: [] },
      textureDataUrl: null,
      chartInited: false
    };
  },
  mounted() {
    this.$nextTick(() => {
      this.initChart();
    });
    this.resizeHandler = this.debounce(this.resize, 200);
    window.addEventListener('resize', this.resizeHandler);
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.resizeHandler);
    if (this.chart) {
      this.chart.dispose();
      this.chart = null;
    }
  },
  methods: {
    // 初始化 3D 地球
    async initChart() {
      const echarts = window.echarts;
      if (!echarts) {
        console.error('Earth3DChart: 未找到全局 echarts，请先引入 echarts 与 echarts-gl');
        return;
      }

      const el = this.$refs.earthChart;
      if (!el || el.clientWidth === 0 || el.clientHeight === 0) {
        // 容器尚未布局完成，延迟重试
        setTimeout(() => this.initChart(), 300);
        return;
      }

      try {
        const [textureCanvas, geoData] = await Promise.all([
          this.buildTexture(),
          this.fetchGeoData()
        ]);
        this.geoData = geoData;

        this.chart = echarts.init(el);
        this.updateChart(textureCanvas);
      } catch (err) {
        console.error('Earth3DChart 初始化失败：', err);
      }
    },

    // 构建带国界的地球纹理画布
    buildTexture() {
      return new Promise((resolve, reject) => {
        const width = 4096;
        const height = 2048;
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');

        // 1. 填充深海底色
        ctx.fillStyle = '#12265f';
        ctx.fillRect(0, 0, width, height);

        // 2. 加载海陆纹理
        const img = new Image();
        // 同源本地图片无需 crossOrigin，避免 CORS 导致画布被污染
        if (this.textureUrl.indexOf('://') !== -1) {
          img.crossOrigin = 'anonymous';
        }
        img.onload = () => {
          ctx.drawImage(img, 0, 0, width, height);
          // 3. 加载并绘制国界
          this.fetchJson(this.geoJsonUrl)
            .then(geoJson => {
              this.drawBorders(ctx, geoJson, width, height);
              resolve(canvas);
            })
            .catch(err => {
              console.warn('Earth3DChart 加载 GeoJSON 失败，将只显示海陆纹理：', err);
              resolve(canvas);
            });
        };
        img.onerror = () => {
          // 纹理加载失败时，至少保留国界线
          this.fetchJson(this.geoJsonUrl)
            .then(geoJson => {
              this.drawBorders(ctx, geoJson, width, height);
              resolve(canvas);
            })
            .catch(() => resolve(canvas));
        };
        img.src = this.textureUrl;
      });
    },

    // 使用 Canvas API 在纹理上绘制国界
    drawBorders(ctx, geoJson, width, height, color = 'rgba(74, 175, 255, 0.65)', lineWidth = 2) {
      ctx.save();
      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.beginPath();

      const project = (lon, lat) => {
        return {
          x: ((lon + 180) / 360) * width,
          y: ((90 - lat) / 180) * height
        };
      };

      const drawRing = (ring) => {
        if (!ring || ring.length < 2) return;
        const start = project(ring[0][0], ring[0][1]);
        ctx.moveTo(start.x, start.y);
        for (let i = 1; i < ring.length; i++) {
          const p = project(ring[i][0], ring[i][1]);
          ctx.lineTo(p.x, p.y);
        }
      };

      for (const feature of geoJson.features || []) {
        const geom = feature.geometry;
        if (!geom) continue;
        if (geom.type === 'Polygon') {
          for (const ring of geom.coordinates) drawRing(ring);
        } else if (geom.type === 'MultiPolygon') {
          for (const polygon of geom.coordinates) {
            for (const ring of polygon) drawRing(ring);
          }
        }
      }

      ctx.stroke();
      ctx.restore();
    },

    // 获取后端地理数据
    async fetchGeoData() {
      try {
        const res = await this.httpGet(this.apiUrl);
        if (res && res.success && res.data) {
          return {
            points: res.data.points || [],
            lines: res.data.lines || []
          };
        }
      } catch (err) {
        console.warn('Earth3DChart 获取地理数据失败：', err);
      }
      return { points: [], lines: [] };
    },

    // 通用 GET 请求封装（优先 axios，其次 fetch）
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

    // 通用 JSON 加载封装
    fetchJson(url) {
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

    // 渲染/更新地球图表
    updateChart(textureCanvas) {
      if (!this.chart) return;

      // 缓存纹理 data URL，避免重复构建与上传导致白屏闪烁
      if (!this.textureDataUrl && textureCanvas) {
        try {
          this.textureDataUrl = textureCanvas.toDataURL('image/png');
        } catch (e) {
          console.warn('Earth3DChart canvas 转 data URL 失败，使用 canvas 对象', e);
        }
      }
      const texture = this.textureDataUrl || textureCanvas;

      const points = this.geoData.points.map(p => ({
        name: p.name,
        value: p.value
      }));

      const lines = this.geoData.lines.map(l => ({
        coords: [l.from, l.to],
        lineStyle: {
          color: l.color || '#568aea'
        }
      }));

      // 已初始化过则只更新数据，不重置 globe，避免纹理重新上传白屏
      if (this.chartInited) {
        this.chart.setOption({
          series: [
            { type: 'scatter3D', coordinateSystem: 'globe', name: '城市采集点', data: points },
            { type: 'lines3D', coordinateSystem: 'globe', name: '采集源飞线', data: lines }
          ]
        }, false);
        return;
      }

      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          show: true,
          trigger: 'item',
          backgroundColor: 'rgba(11, 15, 30, 0.9)',
          borderColor: '#568aea',
          borderWidth: 1,
          textStyle: {
            color: '#d3d6dd'
          },
          formatter: (params) => {
            if (params.seriesType === 'scatter3D') {
              const val = params.value;
              return `<div style="font-weight:bold;color:#fff;margin-bottom:4px">${params.name}</div>
                      <div>经度：${val[0]}</div>
                      <div>纬度：${val[1]}</div>
                      <div>采集量：${val[2] || 0}</div>`;
            }
            if (params.seriesType === 'lines3D') {
              return `<div style="font-weight:bold;color:#fff">采集源飞线</div>
                      <div>${params.data.coords[0][0]},${params.data.coords[0][1]} → ${params.data.coords[1][0]},${params.data.coords[1][1]}</div>`;
            }
            return '';
          }
        },
        globe: {
          baseTexture: texture,
          shading: 'lambert',
          light: {
            ambient: { intensity: 0.5 },
            main: { intensity: 0.8 }
          },
          viewControl: {
            autoRotate: true,
            autoRotateSpeed: 5,
            autoRotateAfterStill: 2,
            rotateSensitivity: 2,
            zoomSensitivity: 2,
            distance: 220,
            alpha: 30,
            beta: 160,
            targetCoord: [116.46, 39.92]
          },
          atmosphere: {
            show: true,
            glowPower: 8,
            color: '#568aea'
          }
        },
        series: [
          {
            type: 'scatter3D',
            coordinateSystem: 'globe',
            name: '城市采集点',
            data: points,
            symbolSize: (val) => Math.max(5, (val[2] || 1) * 1.8),
            itemStyle: {
              color: '#50e3c2',
              opacity: 0.95,
              borderWidth: 1,
              borderColor: '#fff'
            },
            emphasis: {
              itemStyle: {
                color: '#ffeb3b'
              }
            },
            label: {
              show: false
            }
          },
          {
            type: 'lines3D',
            coordinateSystem: 'globe',
            name: '采集源飞线',
            data: lines,
            effect: {
              show: true,
              period: 4,
              trailWidth: 3,
              trailLength: 0.5,
              trailOpacity: 1,
              trailColor: '#568aea'
            },
            lineStyle: {
              width: 1,
              color: '#568aea',
              opacity: 0.4
            }
          }
        ]
      };

      this.chart.setOption(option, true);
      this.chartInited = true;
    },

    // 窗口自适应
    resize() {
      if (this.chart) {
        this.chart.resize();
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
.earth-chart {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

/* 深色星空背景 */
.earth-chart::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
  background:
    radial-gradient(ellipse at bottom, rgba(27, 39, 53, 0.95) 0%, rgba(9, 10, 15, 0.98) 100%),
    radial-gradient(1px 1px at 20px 30px, rgba(255, 255, 255, 0.8), transparent),
    radial-gradient(1px 1px at 40px 70px, rgba(255, 255, 255, 0.6), transparent),
    radial-gradient(1px 1px at 50px 160px, rgba(255, 255, 255, 0.7), transparent),
    radial-gradient(1px 1px at 90px 40px, rgba(255, 255, 255, 0.5), transparent),
    radial-gradient(1px 1px at 130px 80px, rgba(255, 255, 255, 0.7), transparent),
    radial-gradient(1px 1px at 160px 120px, rgba(255, 255, 255, 0.6), transparent);
  background-size: 100% 100%, 200px 200px, 220px 220px, 250px 250px, 180px 180px, 240px 240px, 160px 160px;
}

/* 让 canvas 覆盖在星空背景之上 */
.earth-chart > div {
  position: relative;
  z-index: 1;
}
</style>
