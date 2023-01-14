require(blogdown)
blogdown::install_hugo(force = TRUE)

blogdown::serve_site()
check_site()

blogdown::stop_server()
