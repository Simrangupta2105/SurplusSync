# SurplusSync Frontend Production Container (Nginx)
FROM nginx:alpine

# Copy pre-built production assets
COPY dist /usr/share/nginx/html

# Copy Nginx SPA reverse proxy configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
