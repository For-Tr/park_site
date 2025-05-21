/** axios封装
 * 请求拦截、相应拦截、错误统一处理
 */
// 环境的切换
// axios.defaults.baseURL = 'http://10.10.137.16/cgi-bin/'
axios.defaults.timeout = 50000
// post请求头
axios.defaults.headers.post['Content-Type'] = 'application/x-www-form-urlencoded;charset=UTF-8'
// 请求拦截器
//切割字符串
let getCookie = function (name, token) {
  var value = '; ' + token;
  var parts = value.split('; ' + name + '=');
  if (parts.length === 2) return parts.pop().split(';').shift()
}
axios.interceptors.request.use(
  function(config) {
    // 在post请求前统一添加X-CSRFToken的header信息
    let token = document.cookie;
    if(token && config.method == 'post'){
      config.headers['X-CSRFToken'] = getCookie('csrftoken',token);
    }
    return config;
  },
  function(error) {
    // Do something with request error
    return Promise.reject(error);
  }
);

function axiosget(url, params) {
  return new Promise((resolve, reject) => {
    axios
      .get(url, {
        params: params
      })
      .then(res => {
        resolve(res.data)
      })
      .catch(err => {
        reject(err.data)
      })
  })
}
// qs.stringify(data)
function axiospost(url, data) {
  return new Promise((resolve, reject) => {
    axios
      .post(url, Qs.stringify(data))
      .then(res => {
        resolve(res.data)
      })
      .catch(err => {
        reject(err.data)
      })
  })
}

function axiosdelete(url, data) {
  return new Promise((resolve, reject) => {
    axios
      .delete(url, {data:data})
      .then(res => {
        resolve(res.data)
      })
      .catch(err => {
        reject(err.data)
      })
  })
}

function axiosput(url, data) {
  return new Promise((resolve, reject) => {
    axios
      .put(url, {data:data})
      .then(res => {
        resolve(res.data)
      })
      .catch(err => {
        reject(err.data)
      })
  })
}


String.prototype.format = function(...args) {
    if (args.length == 1 && typeof args[0] == 'object') {
    	let k = '', v = ''
    	return this.replace(/{[A-Za-z]+}/g, (it, i) => {
    		k = it.slice(1, -1)
    		v = args[0][k]
    		return typeof v != 'undefined' ? v : '';
    	})
    }
    return this.replace(/{(\d+)}/g, (it, i) => {
        return typeof args[i] != 'undefined' ? args[i] : '';
    });
};