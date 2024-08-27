--
-- PostgreSQL database dump
--

-- Dumped from database version 15.7 (Debian 15.7-1.pgdg120+1)
-- Dumped by pg_dump version 16.3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: qr_code_inventory_user
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO qr_code_inventory_user;

--
-- Name: inventory; Type: TABLE; Schema: public; Owner: qr_code_inventory_user
--

CREATE TABLE public.inventory (
    id integer NOT NULL,
    batch_number character varying,
    part_number character varying,
    quantity integer
);


ALTER TABLE public.inventory OWNER TO qr_code_inventory_user;

--
-- Name: inventory_id_seq; Type: SEQUENCE; Schema: public; Owner: qr_code_inventory_user
--

CREATE SEQUENCE public.inventory_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.inventory_id_seq OWNER TO qr_code_inventory_user;

--
-- Name: inventory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: qr_code_inventory_user
--

ALTER SEQUENCE public.inventory_id_seq OWNED BY public.inventory.id;


--
-- Name: orders; Type: TABLE; Schema: public; Owner: qr_code_inventory_user
--

CREATE TABLE public.orders (
    id integer NOT NULL,
    order_number character varying,
    customer_name character varying,
    product_name character varying,
    quantity integer
);


ALTER TABLE public.orders OWNER TO qr_code_inventory_user;

--
-- Name: orders_id_seq; Type: SEQUENCE; Schema: public; Owner: qr_code_inventory_user
--

CREATE SEQUENCE public.orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.orders_id_seq OWNER TO qr_code_inventory_user;

--
-- Name: orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: qr_code_inventory_user
--

ALTER SEQUENCE public.orders_id_seq OWNED BY public.orders.id;


--
-- Name: production_orders; Type: TABLE; Schema: public; Owner: qr_code_inventory_user
--

CREATE TABLE public.production_orders (
    id integer NOT NULL,
    order_number character varying,
    drawing_designation character varying,
    quantity integer,
    desired_production_date_start date,
    desired_production_date_end date,
    required_material character varying,
    metal_delivery_date character varying,
    notes character varying,
    publication_date date,
    drawing_link character varying,
    archived_drawings character varying
);


ALTER TABLE public.production_orders OWNER TO qr_code_inventory_user;

--
-- Name: production_orders_id_seq; Type: SEQUENCE; Schema: public; Owner: qr_code_inventory_user
--

CREATE SEQUENCE public.production_orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.production_orders_id_seq OWNER TO qr_code_inventory_user;

--
-- Name: production_orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: qr_code_inventory_user
--

ALTER SEQUENCE public.production_orders_id_seq OWNED BY public.production_orders.id;


--
-- Name: inventory id; Type: DEFAULT; Schema: public; Owner: qr_code_inventory_user
--

ALTER TABLE ONLY public.inventory ALTER COLUMN id SET DEFAULT nextval('public.inventory_id_seq'::regclass);


--
-- Name: orders id; Type: DEFAULT; Schema: public; Owner: qr_code_inventory_user
--

ALTER TABLE ONLY public.orders ALTER COLUMN id SET DEFAULT nextval('public.orders_id_seq'::regclass);


--
-- Name: production_orders id; Type: DEFAULT; Schema: public; Owner: qr_code_inventory_user
--

ALTER TABLE ONLY public.production_orders ALTER COLUMN id SET DEFAULT nextval('public.production_orders_id_seq'::regclass);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: qr_code_inventory_user
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: inventory inventory_pkey; Type: CONSTRAINT; Schema: public; Owner: qr_code_inventory_user
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_pkey PRIMARY KEY (id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: qr_code_inventory_user
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: production_orders production_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: qr_code_inventory_user
--

ALTER TABLE ONLY public.production_orders
    ADD CONSTRAINT production_orders_pkey PRIMARY KEY (id);


--
-- Name: ix_inventory_batch_number; Type: INDEX; Schema: public; Owner: qr_code_inventory_user
--

CREATE INDEX ix_inventory_batch_number ON public.inventory USING btree (batch_number);


--
-- Name: ix_inventory_id; Type: INDEX; Schema: public; Owner: qr_code_inventory_user
--

CREATE INDEX ix_inventory_id ON public.inventory USING btree (id);


--
-- Name: ix_inventory_part_number; Type: INDEX; Schema: public; Owner: qr_code_inventory_user
--

CREATE INDEX ix_inventory_part_number ON public.inventory USING btree (part_number);


--
-- Name: ix_orders_id; Type: INDEX; Schema: public; Owner: qr_code_inventory_user
--

CREATE INDEX ix_orders_id ON public.orders USING btree (id);


--
-- Name: ix_orders_order_number; Type: INDEX; Schema: public; Owner: qr_code_inventory_user
--

CREATE UNIQUE INDEX ix_orders_order_number ON public.orders USING btree (order_number);


--
-- Name: ix_production_orders_id; Type: INDEX; Schema: public; Owner: qr_code_inventory_user
--

CREATE INDEX ix_production_orders_id ON public.production_orders USING btree (id);


--
-- Name: ix_production_orders_order_number; Type: INDEX; Schema: public; Owner: qr_code_inventory_user
--

CREATE UNIQUE INDEX ix_production_orders_order_number ON public.production_orders USING btree (order_number);


--
-- PostgreSQL database dump complete
--

