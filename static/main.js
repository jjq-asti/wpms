function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KBs', 'MB/s', 'GB/s'];

    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}


$(document).ready(function() {
      // socket
      var socket = io.connect('http://localhost:5000', namespaces=['/dashboard']);
      var chart = $('#chart').get(0);

      socket.on('connect', function() {
          console.log('Connected');
          if(chart.getContext){
              render();
              window.onresize = render;
          }
          $('#transport').text('(Connected)');
      });
      socket.on('ping_from_server', function(msg) {

          $('#latency').text(msg.data.toFixed() + 'ms');
      });

      socket.on('my_response', function(msg) {
          $('#log').append('<br>Received: ' + msg.data)
          socket.emit('join_dashboard')
      });

      socket.on('disconnect', function() {
          $('#transport').text('(disconnected)');
      });

      socket.on('dl_result', function(msg) {
          $('#dl_speed').text(formatBytes(msg.data));
      });
      socket.on('ul_result', function(msg) {
          $('#ul_speed').text(formatBytes(msg.data));
      });
      socket.on('speedtest_error', function(){
          alert('An error occured, Please try again.')
      })
      socket.on('client_latency', function(msg){
        if (time)
            time.append(+new Date, msg.data);
    })

      socket.on('ping_result', function(msg){
        console.log(msg.data);
        // time.append(+new Date, msg.data);
    })


      $('form#emit').submit(function(event) {
          socket.emit('tasks_event', {'task': 1, 'data': 'None'});
          console.log('start speedtest');
          return false;
      });

      $('form#ping').submit(function(event) {
          console.log('start ping');
          socket.emit('tasks_event', {'task': 2, 'data': "202.90.158.6"});
          return false;
      });
        // chart
    var smoothie;
    var time;
    function render() {
        if (smoothie)
            smoothie.stop();
        chart.width = document.body.clientWidth;
        smoothie = new SmoothieChart({labels:{fontSize:36}});
        smoothie.streamTo(chart, 1000);
        time = new TimeSeries();
        smoothie.addTimeSeries(time, {
            strokeStyle: 'rgb(255, 0, 0)',
            fillStyle: 'rgba(255, 0, 0, 0.4)',
            lineWidth: 2
        });
    }
})
